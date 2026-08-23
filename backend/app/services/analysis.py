"""Quant engine: prices/returns in, risk/return numbers out. No FastAPI here, keep it unit-testable."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.optimize import minimize

from app.services.cache import PRICE_HISTORY_CACHE, cached_call

logger = logging.getLogger(__name__)

TRADING_DAYS_PER_YEAR = 252

# below ~2mo of history, vol/correlation estimates get too noisy
MIN_PRICE_POINTS = 30

DEFAULT_RISK_FREE_RATE = 0.04

# Nudges the covariance matrix's diagonal so Cholesky doesn't choke on a holding with exactly
# zero return variance (flat/stale prices). Negligible next to real daily variances (~1e-4+).
COVARIANCE_JITTER = 1e-8


class InsufficientDataError(Exception):
    pass


def closes_from_history(ticker: str, history: pd.DataFrame) -> pd.Series | None:
    """Shared by analysis._fetch_single_ticker_closes and backtest's date-range equivalent:
    pulls Close out of a yfinance history frame, enforces the min-points floor, and
    normalizes the tz-aware index to plain dates so frames line up on join."""
    closes = history.get("Close")
    if closes is None or closes.dropna().shape[0] < MIN_PRICE_POINTS:
        logger.warning("Ticker %s returned too little price history (%s points); skipping", ticker, 0 if closes is None else closes.dropna().shape[0])
        return None

    closes.index = closes.index.tz_localize(None).normalize()
    return closes


@cached_call(PRICE_HISTORY_CACHE, key_prefix="price_history")
def _fetch_single_ticker_closes(ticker: str, period: str) -> pd.Series | None:
    """Cached so repeat requests don't re-hit yfinance."""
    try:
        history = yf.Ticker(ticker).history(period=period, auto_adjust=True)
    except Exception as exc:  # yfinance raises a mix of exception types depending on the failure
        logger.warning("Failed to fetch price history for %s: %s", ticker, exc)
        return None
    return closes_from_history(ticker, history)


def fetch_price_history(tickers: list[str], years: int) -> tuple[pd.DataFrame, list[str]]:
    """Daily adjusted-close prices per ticker, aligned into one DataFrame. Bad tickers get skipped, not raised.

    Returns (prices, skipped_tickers).
    """
    period = f"{years}y"
    series_by_ticker: dict[str, pd.Series] = {}
    skipped: list[str] = []

    for ticker in tickers:
        closes = _fetch_single_ticker_closes(ticker, period)
        if closes is None:
            skipped.append(ticker)
            continue
        series_by_ticker[ticker] = closes

    if not series_by_ticker:
        raise InsufficientDataError("None of the requested tickers returned usable price data")

    # drop dates not shared by every ticker (holidays, IPOs mid-window) so columns stay equal length
    prices = pd.DataFrame(series_by_ticker).sort_index().dropna(how="any")

    if prices.shape[0] < MIN_PRICE_POINTS:
        raise InsufficientDataError(
            f"Only {prices.shape[0]} overlapping trading days across the requested tickers; "
            f"need at least {MIN_PRICE_POINTS}"
        )

    return prices, skipped


def compute_returns(prices: pd.DataFrame) -> pd.DataFrame:
    # Simple returns, not log, so they stay linear for portfolio_return = weights . returns.
    return prices.pct_change().dropna(how="all")


def annualize_return(daily_returns: pd.Series | np.ndarray) -> float:
    # Keep expected returns linear for portfolio optimization (arithmetic, not geometric, mean).
    return float(np.mean(daily_returns)) * TRADING_DAYS_PER_YEAR


def annualize_volatility(daily_returns: pd.Series | np.ndarray) -> float:
    return float(np.std(daily_returns, ddof=1)) * np.sqrt(TRADING_DAYS_PER_YEAR)


def sharpe_ratio(annual_return: float, annual_vol: float, risk_free_rate: float = DEFAULT_RISK_FREE_RATE) -> float:
    if annual_vol == 0:
        return 0.0
    return (annual_return - risk_free_rate) / annual_vol


def correlation_matrix(returns: pd.DataFrame) -> pd.DataFrame:
    return returns.corr()


@dataclass
class OptimalPortfolioResult:
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    weights: dict[str, float]


@dataclass
class EfficientFrontierResult:
    points: list[tuple[float, float]]  # (annual_return, annual_volatility)
    max_sharpe: OptimalPortfolioResult
    min_volatility: OptimalPortfolioResult


def _portfolio_return(weights: np.ndarray, mean_returns: np.ndarray) -> float:
    return float(weights @ mean_returns)


def _portfolio_volatility(weights: np.ndarray, cov_matrix: np.ndarray) -> float:
    variance = weights @ cov_matrix @ weights
    return float(np.sqrt(max(variance, 0.0)))


def _solve_min_volatility(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    n_assets: int,
    target_return: float | None,
) -> np.ndarray | None:
    """Min-volatility weights, long-only, summing to 1, optionally hitting an exact target return."""
    x0 = np.full(n_assets, 1.0 / n_assets)
    bounds = [(0.0, 1.0)] * n_assets  # long-only

    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]
    if target_return is not None:
        constraints.append({"type": "eq", "fun": lambda w: w @ mean_returns - target_return})

    result = minimize(
        _portfolio_volatility,
        x0,
        args=(cov_matrix,),
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-10},
    )
    return result.x if result.success else None


def _solve_max_sharpe(
    mean_returns: np.ndarray,
    cov_matrix: np.ndarray,
    n_assets: int,
    risk_free_rate: float,
) -> np.ndarray | None:
    """Max-Sharpe weights (scipy only minimizes, so minimize negative Sharpe)."""
    def neg_sharpe(w: np.ndarray) -> float:
        ret = _portfolio_return(w, mean_returns)
        vol = _portfolio_volatility(w, cov_matrix)
        if vol == 0:
            return 0.0
        return -(ret - risk_free_rate) / vol

    x0 = np.full(n_assets, 1.0 / n_assets)
    bounds = [(0.0, 1.0)] * n_assets
    constraints = [{"type": "eq", "fun": lambda w: np.sum(w) - 1.0}]

    result = minimize(
        neg_sharpe,
        x0,
        method="SLSQP",
        bounds=bounds,
        constraints=constraints,
        options={"maxiter": 500, "ftol": 1e-10},
    )
    return result.x if result.success else None


def efficient_frontier(
    returns: pd.DataFrame,
    n_portfolios: int = 50,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> EfficientFrontierResult:
    """Sweep target returns, solve min-vol weights at each, plus locate max-Sharpe and min-vol portfolios."""
    tickers = list(returns.columns)
    n_assets = len(tickers)
    mean_returns = returns.mean().to_numpy() * TRADING_DAYS_PER_YEAR
    cov_matrix = returns.cov().to_numpy() * TRADING_DAYS_PER_YEAR

    if n_assets == 1:
        # single holding, frontier is just one point
        ret, vol = float(mean_returns[0]), float(np.sqrt(cov_matrix[0, 0]))
        only = OptimalPortfolioResult(ret, vol, sharpe_ratio(ret, vol, risk_free_rate), {tickers[0]: 1.0})
        return EfficientFrontierResult(points=[(ret, vol)], max_sharpe=only, min_volatility=only)

    target_returns = np.linspace(mean_returns.min(), mean_returns.max(), n_portfolios)

    points: list[tuple[float, float]] = []
    for target in target_returns:
        weights = _solve_min_volatility(mean_returns, cov_matrix, n_assets, target_return=float(target))
        if weights is None:
            continue  # didn't converge for this target, skip it
        vol = _portfolio_volatility(weights, cov_matrix)
        points.append((float(target), vol))

    max_sharpe_weights = _solve_max_sharpe(mean_returns, cov_matrix, n_assets, risk_free_rate)
    min_vol_weights = _solve_min_volatility(mean_returns, cov_matrix, n_assets, target_return=None)

    if max_sharpe_weights is None or min_vol_weights is None:
        raise RuntimeError("Portfolio optimizer failed to converge on max-Sharpe/min-volatility solutions")

    def to_result(weights: np.ndarray) -> OptimalPortfolioResult:
        ret = _portfolio_return(weights, mean_returns)
        vol = _portfolio_volatility(weights, cov_matrix)
        return OptimalPortfolioResult(
            annual_return=ret,
            annual_volatility=vol,
            sharpe_ratio=sharpe_ratio(ret, vol, risk_free_rate),
            weights={ticker: float(w) for ticker, w in zip(tickers, weights)},
        )

    return EfficientFrontierResult(
        points=points,
        max_sharpe=to_result(max_sharpe_weights),
        min_volatility=to_result(min_vol_weights),
    )


@dataclass
class MonteCarloBandResult:
    day: int
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float


@dataclass
class MonteCarloResult:
    starting_value: float
    bands: list[MonteCarloBandResult] = field(default_factory=list)
    value_at_risk_95: float = 0.0


def monte_carlo_simulation(
    returns: pd.DataFrame,
    weights: dict[str, float],
    years: int = 10,
    n_simulations: int = 10_000,
    n_checkpoints: int = 50,
    seed: int | None = None,
) -> MonteCarloResult:
    """Simulate portfolio value paths via GBM, return percentile bands + 1yr 95% VaR.

    Fully vectorized (sim x checkpoint x asset), no Python loop over simulations.
    """
    rng = np.random.default_rng(seed)
    tickers = list(returns.columns)
    n_assets = len(tickers)
    weight_vector = np.array([weights[t] for t in tickers])

    mean_daily = returns.mean().to_numpy()  # (n_assets,)
    cov_daily = returns.cov().to_numpy()  # (n_assets, n_assets)

    # Ito correction: mu - 0.5*sigma^2, otherwise exp() of drifted log-returns overstates expected price
    drift_daily = mean_daily - 0.5 * np.diag(cov_daily)

    # Apply the historical correlation structure to the simulated noise.
    chol = np.linalg.cholesky(cov_daily + COVARIANCE_JITTER * np.eye(n_assets))

    total_days = years * TRADING_DAYS_PER_YEAR

    # even grid across the horizon + the exact 1yr mark for VaR
    checkpoint_days = np.linspace(0, total_days, n_checkpoints, dtype=int)
    if TRADING_DAYS_PER_YEAR not in checkpoint_days and TRADING_DAYS_PER_YEAR <= total_days:
        checkpoint_days = np.sort(np.unique(np.append(checkpoint_days, TRADING_DAYS_PER_YEAR)))
    else:
        checkpoint_days = np.unique(checkpoint_days)

    step_lengths = np.diff(checkpoint_days)  # dt per step, in trading days
    n_steps = len(step_lengths)

    z = rng.standard_normal((n_simulations, n_steps, n_assets))
    correlated_noise = z @ chol.T
    del z  # (n_simulations, n_steps, n_assets) can be sizeable; drop it once its one use is done

    sqrt_dt = np.sqrt(step_lengths)[None, :, None]
    dt = step_lengths[None, :, None]

    # build log-returns, then cumsum, then exp in place on the same buffer -- one big
    # (sim x checkpoint x asset) array alive at a time instead of four
    correlated_noise *= sqrt_dt
    correlated_noise += drift_daily[None, None, :] * dt
    asset_growth = correlated_noise
    np.cumsum(asset_growth, axis=1, out=asset_growth)
    np.exp(asset_growth, out=asset_growth)

    # prepend day 0 = growth multiple of 1.0
    ones = np.ones((n_simulations, 1, n_assets))
    asset_growth = np.concatenate([ones, asset_growth], axis=1)

    # buy-and-hold, not rebalanced-to-target
    portfolio_value = asset_growth @ weight_vector

    percentiles = np.percentile(portfolio_value, [5, 25, 50, 75, 95], axis=0)
    bands = [
        MonteCarloBandResult(
            day=int(day),
            p5=float(percentiles[0, i]),
            p25=float(percentiles[1, i]),
            p50=float(percentiles[2, i]),
            p75=float(percentiles[3, i]),
            p95=float(percentiles[4, i]),
        )
        for i, day in enumerate(checkpoint_days)
    ]

    one_year_idx = int(np.where(checkpoint_days == TRADING_DAYS_PER_YEAR)[0][0])
    one_year_p5 = float(np.percentile(portfolio_value[:, one_year_idx], 5))
    value_at_risk_95 = 1.0 - one_year_p5

    return MonteCarloResult(starting_value=1.0, bands=bands, value_at_risk_95=value_at_risk_95)
