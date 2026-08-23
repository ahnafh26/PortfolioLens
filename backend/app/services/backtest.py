"""Historical stress-period backtesting vs S&P 500. Reuses analysis.py's return math, new stuff is alpha/beta/drawdown."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field

import numpy as np
import pandas as pd
import yfinance as yf

from app.services.analysis import (
    DEFAULT_RISK_FREE_RATE,
    MIN_PRICE_POINTS,
    InsufficientDataError,
    annualize_return,
    closes_from_history,
    compute_returns,
)
from app.services.cache import PRICE_HISTORY_CACHE, cached_call

logger = logging.getLogger(__name__)

BENCHMARK_TICKER = "SPY"

# (label, start, end). dates are the commonly-cited peak/trough markers, close enough
STRESS_PERIODS: dict[str, tuple[str, str, str]] = {
    "gfc_2008": ("2008 Financial Crisis", "2007-10-09", "2009-03-09"),
    "covid_2020": ("2020 COVID Crash", "2020-02-19", "2020-04-30"),
    "rate_hikes_2022": ("2022 Rate Hikes", "2022-01-01", "2022-12-31"),
}


@cached_call(PRICE_HISTORY_CACHE, key_prefix="price_history_range")
def _fetch_single_ticker_closes_range(ticker: str, start: str, end: str) -> pd.Series | None:
    """Like analysis._fetch_single_ticker_closes but for an exact date range instead of a lookback period."""
    try:
        history = yf.Ticker(ticker).history(start=start, end=end, auto_adjust=True)
    except Exception as exc:
        logger.warning("Failed to fetch price history for %s (%s to %s): %s", ticker, start, end, exc)
        return None
    return closes_from_history(ticker, history)


def fetch_price_history_range(tickers: list[str], start: str, end: str) -> tuple[pd.DataFrame, list[str]]:
    """Same contract as analysis.fetch_price_history, explicit [start, end) window."""
    series_by_ticker: dict[str, pd.Series] = {}
    skipped: list[str] = []

    for ticker in tickers:
        closes = _fetch_single_ticker_closes_range(ticker, start, end)
        if closes is None:
            skipped.append(ticker)
            continue
        series_by_ticker[ticker] = closes

    if not series_by_ticker:
        raise InsufficientDataError(f"None of the requested tickers returned usable price data for {start} to {end}")

    prices = pd.DataFrame(series_by_ticker).sort_index().dropna(how="any")
    if prices.shape[0] < MIN_PRICE_POINTS:
        raise InsufficientDataError(
            f"Only {prices.shape[0]} overlapping trading days between {start} and {end}; need at least {MIN_PRICE_POINTS}"
        )
    return prices, skipped


def compute_beta(portfolio_returns: pd.Series | np.ndarray, benchmark_returns: pd.Series | np.ndarray) -> float:
    """cov(portfolio, benchmark) / var(benchmark)."""
    benchmark_var = float(np.var(benchmark_returns, ddof=1))
    if benchmark_var == 0:
        return 0.0
    covariance = float(np.cov(portfolio_returns, benchmark_returns, ddof=1)[0, 1])
    return covariance / benchmark_var


def compute_alpha(
    portfolio_annual_return: float,
    benchmark_annual_return: float,
    beta: float,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> float:
    """Jensen's alpha: return in excess of what CAPM predicts given beta."""
    expected_return = risk_free_rate + beta * (benchmark_annual_return - risk_free_rate)
    return portfolio_annual_return - expected_return


def max_drawdown(cumulative_values: pd.Series | np.ndarray) -> float:
    """Largest peak-to-trough decline, as a positive fraction."""
    values = np.asarray(cumulative_values, dtype=float)
    running_max = np.maximum.accumulate(values)
    drawdowns = (values - running_max) / running_max
    return float(-drawdowns.min())


def _value_path(daily_returns: np.ndarray) -> np.ndarray:
    """Cumulative growth of $1, with day zero prepended at 1.0."""
    growth = np.cumprod(1.0 + daily_returns)
    return np.concatenate([[1.0], growth])


@dataclass
class BacktestResult:
    dates: list[str]  # ISO dates, length = len(portfolio_path) == len(benchmark_path)
    portfolio_path: list[float]
    benchmark_path: list[float]
    portfolio_total_return: float
    benchmark_total_return: float
    portfolio_max_drawdown: float
    benchmark_max_drawdown: float
    alpha: float
    beta: float
    skipped_tickers: list[str] = field(default_factory=list)


def run_backtest(
    tickers: list[str],
    weights: dict[str, float],
    start: str,
    end: str,
    benchmark_ticker: str = BENCHMARK_TICKER,
    risk_free_rate: float = DEFAULT_RISK_FREE_RATE,
) -> BacktestResult:
    # benchmark fetched alongside holdings so it goes through the same date-align join
    all_tickers = list(dict.fromkeys([*tickers, benchmark_ticker]))
    prices, skipped = fetch_price_history_range(all_tickers, start, end)

    if benchmark_ticker not in prices.columns:
        raise InsufficientDataError(f"Benchmark {benchmark_ticker} had no usable price data for {start} to {end}")

    valid_holding_tickers = [t for t in tickers if t in prices.columns]
    if not valid_holding_tickers:
        raise InsufficientDataError("None of the requested holdings had usable price data for this period")

    # rescale weights across survivors, same as /analyze
    raw_weights = {t: weights[t] for t in valid_holding_tickers}
    total_weight = sum(raw_weights.values())
    normalized_weights = {t: w / total_weight for t, w in raw_weights.items()}

    holding_returns = compute_returns(prices[valid_holding_tickers])
    benchmark_returns = compute_returns(prices[[benchmark_ticker]])[benchmark_ticker]

    weight_vector = np.array([normalized_weights[t] for t in holding_returns.columns])
    portfolio_daily_returns = holding_returns.to_numpy() @ weight_vector

    portfolio_annual_return = annualize_return(portfolio_daily_returns)
    benchmark_annual_return = annualize_return(benchmark_returns)
    beta = compute_beta(portfolio_daily_returns, benchmark_returns.to_numpy())
    alpha = compute_alpha(portfolio_annual_return, benchmark_annual_return, beta, risk_free_rate)

    portfolio_path = _value_path(portfolio_daily_returns)
    benchmark_path = _value_path(benchmark_returns.to_numpy())

    date_index = holding_returns.index
    first_date = prices.index[0]
    dates = [first_date.date().isoformat()] + [d.date().isoformat() for d in date_index]

    return BacktestResult(
        dates=dates,
        portfolio_path=portfolio_path.tolist(),
        benchmark_path=benchmark_path.tolist(),
        portfolio_total_return=float(portfolio_path[-1] - 1.0),
        benchmark_total_return=float(benchmark_path[-1] - 1.0),
        portfolio_max_drawdown=max_drawdown(portfolio_path),
        benchmark_max_drawdown=max_drawdown(benchmark_path),
        alpha=alpha,
        beta=beta,
        skipped_tickers=[t for t in skipped if t != benchmark_ticker],
    )
