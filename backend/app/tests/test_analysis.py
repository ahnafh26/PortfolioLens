"""Tests for analysis.py. Hand-computed values where practical, invariants (sums to 1, monotonic, etc) otherwise."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services import analysis


# compute_returns

def test_compute_returns_hand_computed():
    prices = pd.DataFrame(
        {"A": [100.0, 110.0, 121.0], "B": [50.0, 45.0, 49.5]},
        index=pd.date_range("2024-01-01", periods=3),
    )
    returns = analysis.compute_returns(prices)

    # A: +10%, then +10% again. B: -10%, then +10%
    assert returns.shape == (2, 2)
    assert returns["A"].tolist() == pytest.approx([0.10, 0.10])
    assert returns["B"].tolist() == pytest.approx([-0.10, 0.10])


# annualize_return / annualize_volatility

def test_annualize_return_hand_computed():
    daily = pd.Series([0.01, 0.02, 0.03, 0.04])  # mean 0.025
    assert analysis.annualize_return(daily) == pytest.approx(0.025 * 252)


def test_annualize_volatility_hand_computed():
    daily = pd.Series([0.01, 0.02, 0.03, 0.04])
    expected_daily_std = 0.0129099444874  # sample std (ddof=1), computed independently
    assert analysis.annualize_volatility(daily) == pytest.approx(expected_daily_std * np.sqrt(252), rel=1e-6)


# sharpe_ratio

def test_sharpe_ratio_basic():
    assert analysis.sharpe_ratio(annual_return=0.12, annual_vol=0.08, risk_free_rate=0.04) == pytest.approx(1.0)


def test_sharpe_ratio_uses_default_risk_free_rate():
    # default rf is 0.04
    assert analysis.sharpe_ratio(annual_return=0.10, annual_vol=0.10) == pytest.approx(0.6)


def test_sharpe_ratio_zero_volatility_is_guarded():
    # A zero-volatility "portfolio" shouldn't raise a division-by-zero error.
    assert analysis.sharpe_ratio(annual_return=0.10, annual_vol=0.0) == 0.0


# correlation_matrix

def test_correlation_matrix_matches_independent_numpy_computation():
    a = [0.02, 0.01, 0.03, 0.00, 0.02, 0.01]
    b = [0.01, 0.02, 0.00, 0.03, 0.01, 0.02]
    returns = pd.DataFrame({"A": a, "B": b})

    result = analysis.correlation_matrix(returns)

    # cross-check against numpy.corrcoef, different code path than pandas' .corr()
    expected = float(np.corrcoef(a, b)[0, 1])
    assert result.loc["A", "B"] == pytest.approx(expected)
    assert result.loc["A", "A"] == pytest.approx(1.0)  # a series is always perfectly correlated with itself


def test_correlation_matrix_perfect_negative_correlation():
    a = [0.01, -0.01, 0.02, -0.02, 0.01, -0.01]
    b = [-x for x in a]
    returns = pd.DataFrame({"A": a, "B": b})

    result = analysis.correlation_matrix(returns)
    assert result.loc["A", "B"] == pytest.approx(-1.0)


# efficient_frontier

@pytest.fixture
def two_asset_returns() -> pd.DataFrame:
    """Two holdings, imperfect correlation, so diversification should measurably reduce volatility."""
    rng = np.random.default_rng(seed=7)
    n = 200
    shared = rng.normal(0, 0.01, n)
    a = 0.0010 + shared + rng.normal(0, 0.004, n)
    b = 0.0006 - 0.5 * shared + rng.normal(0, 0.006, n)
    return pd.DataFrame({"A": a, "B": b})


def test_efficient_frontier_optimal_weights_are_valid_allocations(two_asset_returns):
    result = analysis.efficient_frontier(two_asset_returns, n_portfolios=20)

    for portfolio in (result.max_sharpe, result.min_volatility):
        weight_values = list(portfolio.weights.values())
        assert sum(weight_values) == pytest.approx(1.0, abs=1e-4)  # fully invested
        assert all(-1e-9 <= w <= 1 + 1e-9 for w in weight_values)  # long-only, no leverage


def test_efficient_frontier_min_volatility_beats_every_individual_holding(two_asset_returns):
    """With correlation < 1, some mix should beat either asset alone."""
    result = analysis.efficient_frontier(two_asset_returns, n_portfolios=20)

    individual_vols = [
        analysis.annualize_volatility(two_asset_returns[col]) for col in two_asset_returns.columns
    ]
    assert result.min_volatility.annual_volatility < min(individual_vols)


def test_efficient_frontier_max_sharpe_beats_naive_equal_weight(two_asset_returns):
    """Optimizer shouldn't do worse than naive equal-weight, in-sample."""
    result = analysis.efficient_frontier(two_asset_returns, n_portfolios=20)

    mean_returns = two_asset_returns.mean().to_numpy() * analysis.TRADING_DAYS_PER_YEAR
    cov_matrix = two_asset_returns.cov().to_numpy() * analysis.TRADING_DAYS_PER_YEAR
    equal_weights = np.array([0.5, 0.5])
    equal_return = float(equal_weights @ mean_returns)
    equal_vol = float(np.sqrt(equal_weights @ cov_matrix @ equal_weights))
    equal_sharpe = analysis.sharpe_ratio(equal_return, equal_vol)

    assert result.max_sharpe.sharpe_ratio >= equal_sharpe - 1e-6


def test_efficient_frontier_points_span_the_achievable_return_range(two_asset_returns):
    result = analysis.efficient_frontier(two_asset_returns, n_portfolios=20)
    returns_seen = [pt[0] for pt in result.points]

    mean_returns = two_asset_returns.mean().to_numpy() * analysis.TRADING_DAYS_PER_YEAR
    assert min(returns_seen) == pytest.approx(mean_returns.min(), abs=1e-6)
    assert max(returns_seen) == pytest.approx(mean_returns.max(), abs=1e-6)


def test_efficient_frontier_single_asset_degenerates_to_one_point():
    returns = pd.DataFrame({"A": [0.01, -0.01, 0.02, -0.02, 0.01]})
    result = analysis.efficient_frontier(returns, n_portfolios=20)

    assert result.points == [(result.max_sharpe.annual_return, result.max_sharpe.annual_volatility)]
    assert result.max_sharpe.weights == {"A": 1.0}
    assert result.min_volatility.weights == {"A": 1.0}


def test_efficient_frontier_respects_long_only_bounds():
    """One holding is a clear loser; an unconstrained solver would short it to lever up on the other."""
    rng = np.random.default_rng(3)
    n = 200
    returns = pd.DataFrame(
        {"GOOD": rng.normal(0.003, 0.01, n), "BAD": rng.normal(-0.002, 0.015, n)}
    )

    result = analysis.efficient_frontier(returns, n_portfolios=15)

    for portfolio in (result.max_sharpe, result.min_volatility):
        for weight in portfolio.weights.values():
            assert -1e-6 <= weight <= 1 + 1e-6


def test_efficient_frontier_handles_a_zero_volatility_holding():
    """A holding with a flat price history makes the covariance matrix singular; the optimizer
    should still solve rather than error out (unlike Monte Carlo's Cholesky step)."""
    rng = np.random.default_rng(3)
    returns = pd.DataFrame({"CASH": [0.0] * 60, "AAPL": rng.normal(0.001, 0.02, 60)})

    result = analysis.efficient_frontier(returns, n_portfolios=10)

    assert sum(result.max_sharpe.weights.values()) == pytest.approx(1.0, abs=1e-6)
    assert result.min_volatility.annual_volatility == pytest.approx(0.0, abs=1e-6)


# monte_carlo_simulation

@pytest.fixture
def mc_returns() -> pd.DataFrame:
    rng = np.random.default_rng(seed=42)
    n = 250
    a = rng.normal(0.0006, 0.012, n)
    b = rng.normal(0.0004, 0.009, n)
    return pd.DataFrame({"A": a, "B": b})


def test_monte_carlo_day_zero_has_no_spread(mc_returns):
    """t=0, no time elapsed, band should have zero width."""
    result = analysis.monte_carlo_simulation(
        mc_returns, weights={"A": 0.6, "B": 0.4}, years=1, n_simulations=2_000, seed=1
    )
    day_zero = result.bands[0]
    assert day_zero.day == 0
    assert day_zero.p5 == day_zero.p25 == day_zero.p50 == day_zero.p75 == day_zero.p95 == pytest.approx(1.0)


def test_monte_carlo_percentile_bands_are_monotonic(mc_returns):
    result = analysis.monte_carlo_simulation(
        mc_returns, weights={"A": 0.6, "B": 0.4}, years=2, n_simulations=2_000, seed=1
    )
    for band in result.bands:
        assert band.p5 <= band.p25 <= band.p50 <= band.p75 <= band.p95


def test_monte_carlo_var_matches_the_one_year_checkpoint_band(mc_returns):
    """The reported VaR figure should be internally consistent with the
    fan-chart band at the 1-year (day 252) checkpoint: VaR = 1 - p5."""
    result = analysis.monte_carlo_simulation(
        mc_returns, weights={"A": 0.6, "B": 0.4}, years=1, n_simulations=5_000, seed=3
    )
    one_year_band = next(b for b in result.bands if b.day == analysis.TRADING_DAYS_PER_YEAR)
    assert result.value_at_risk_95 == pytest.approx(1.0 - one_year_band.p5)


def test_monte_carlo_handles_single_asset_portfolio():
    """A one-holding portfolio has a 1x1 covariance matrix; Cholesky still needs to work on that."""
    returns = pd.DataFrame({"A": [0.001, -0.004, 0.006, -0.002, 0.003, 0.0, -0.001, 0.005] * 10})

    result = analysis.monte_carlo_simulation(returns, weights={"A": 1.0}, years=1, n_simulations=2_000, seed=5)

    day_zero = result.bands[0]
    assert day_zero.p5 == day_zero.p95 == pytest.approx(1.0)
    for band in result.bands:
        assert band.p5 <= band.p50 <= band.p95


def test_monte_carlo_handles_a_zero_volatility_holding():
    """A holding with a flat price history makes the covariance matrix singular, which used to
    crash the Cholesky step with LinAlgError. It should degenerate gracefully instead."""
    rng = np.random.default_rng(7)
    returns = pd.DataFrame({"CASH": [0.0] * 60, "AAPL": rng.normal(0.001, 0.02, 60)})

    result = analysis.monte_carlo_simulation(
        returns, weights={"CASH": 0.5, "AAPL": 0.5}, years=1, n_simulations=2_000, seed=5
    )

    for band in result.bands:
        assert band.p5 <= band.p50 <= band.p95
    assert 0.0 < result.value_at_risk_95 < 1.0


def test_monte_carlo_is_deterministic_given_a_seed(mc_returns):
    weights = {"A": 0.6, "B": 0.4}
    result_1 = analysis.monte_carlo_simulation(mc_returns, weights, years=1, n_simulations=500, seed=99)
    result_2 = analysis.monte_carlo_simulation(mc_returns, weights, years=1, n_simulations=500, seed=99)
    assert result_1.value_at_risk_95 == pytest.approx(result_2.value_at_risk_95)


def _reference_monte_carlo_bands(returns, weights, years, n_simulations, seed):
    """Un-optimized reference implementation (allocates a fresh array at every step,
    instead of reusing one buffer in place) -- pins down that the in-place version in
    monte_carlo_simulation produces identical numbers, not just a plausible-looking result."""
    rng = np.random.default_rng(seed)
    tickers = list(returns.columns)
    n_assets = len(tickers)
    weight_vector = np.array([weights[t] for t in tickers])

    mean_daily = returns.mean().to_numpy()
    cov_daily = returns.cov().to_numpy()
    drift_daily = mean_daily - 0.5 * np.diag(cov_daily)
    chol = np.linalg.cholesky(cov_daily + analysis.COVARIANCE_JITTER * np.eye(n_assets))

    total_days = years * analysis.TRADING_DAYS_PER_YEAR
    n_checkpoints = 50
    checkpoint_days = np.linspace(0, total_days, n_checkpoints, dtype=int)
    if analysis.TRADING_DAYS_PER_YEAR not in checkpoint_days and analysis.TRADING_DAYS_PER_YEAR <= total_days:
        checkpoint_days = np.sort(np.unique(np.append(checkpoint_days, analysis.TRADING_DAYS_PER_YEAR)))
    else:
        checkpoint_days = np.unique(checkpoint_days)
    step_lengths = np.diff(checkpoint_days)
    n_steps = len(step_lengths)

    z = rng.standard_normal((n_simulations, n_steps, n_assets))
    correlated_noise = z @ chol.T
    sqrt_dt = np.sqrt(step_lengths)[None, :, None]
    dt = step_lengths[None, :, None]
    log_returns = drift_daily[None, None, :] * dt + correlated_noise * sqrt_dt
    cumulative_log_returns = np.cumsum(log_returns, axis=1)
    asset_growth = np.exp(cumulative_log_returns)
    ones = np.ones((n_simulations, 1, n_assets))
    asset_growth = np.concatenate([ones, asset_growth], axis=1)
    portfolio_value = asset_growth @ weight_vector

    return np.percentile(portfolio_value, [5, 25, 50, 75, 95], axis=0)


def test_monte_carlo_in_place_arrays_match_the_unoptimized_reference(mc_returns):
    weights = {"A": 0.6, "B": 0.4}
    result = analysis.monte_carlo_simulation(mc_returns, weights, years=2, n_simulations=1_000, seed=7)
    reference_percentiles = _reference_monte_carlo_bands(mc_returns, weights, years=2, n_simulations=1_000, seed=7)

    actual = np.array([[b.p5, b.p25, b.p50, b.p75, b.p95] for b in result.bands]).T
    assert np.array_equal(actual, reference_percentiles)


# fetch_price_history (yfinance mocked, no network)

class _FakeYfTicker:
    def __init__(self, symbol: str):
        self.symbol = symbol

    def history(self, period: str, auto_adjust: bool) -> pd.DataFrame:
        if self.symbol == "BADTICKER":
            return pd.DataFrame()  # simulates yfinance's response for an unknown symbol
        if self.symbol == "TOOSHORT":
            dates = pd.date_range("2024-01-01", periods=5, freq="D", tz="UTC")
            return pd.DataFrame({"Close": np.full(5, 100.0)}, index=dates)

        dates = pd.date_range("2023-01-01", periods=40, freq="D", tz="UTC")
        base = 100.0 if self.symbol == "AAA" else 50.0
        return pd.DataFrame({"Close": base + np.arange(40, dtype=float)}, index=dates)


def test_fetch_price_history_skips_bad_ticker_without_crashing(monkeypatch):
    monkeypatch.setattr(analysis.yf, "Ticker", _FakeYfTicker)

    prices, skipped = analysis.fetch_price_history(["AAA", "BBB", "BADTICKER"], years=1)

    assert skipped == ["BADTICKER"]
    assert list(prices.columns) == ["AAA", "BBB"]
    assert prices.shape[0] == 40


def test_fetch_price_history_skips_ticker_with_too_little_history(monkeypatch):
    monkeypatch.setattr(analysis.yf, "Ticker", _FakeYfTicker)

    prices, skipped = analysis.fetch_price_history(["AAA", "TOOSHORT"], years=1)

    assert skipped == ["TOOSHORT"]
    assert list(prices.columns) == ["AAA"]


def test_fetch_price_history_raises_when_nothing_is_usable(monkeypatch):
    monkeypatch.setattr(analysis.yf, "Ticker", _FakeYfTicker)

    with pytest.raises(analysis.InsufficientDataError):
        analysis.fetch_price_history(["BADTICKER", "TOOSHORT"], years=1)


class _StaggeredStartYfTicker:
    """AAA has a full year of history; RECENT only started trading partway through (e.g. a recent IPO)."""

    def __init__(self, symbol: str):
        self.symbol = symbol

    def history(self, period: str, auto_adjust: bool) -> pd.DataFrame:
        if self.symbol == "RECENT":
            dates = pd.date_range("2023-01-21", periods=40, freq="D", tz="UTC")
            return pd.DataFrame({"Close": 50.0 + np.arange(40, dtype=float)}, index=dates)

        dates = pd.date_range("2023-01-01", periods=60, freq="D", tz="UTC")
        return pd.DataFrame({"Close": 100.0 + np.arange(60, dtype=float)}, index=dates)


def test_fetch_price_history_aligns_tickers_with_different_start_dates(monkeypatch):
    monkeypatch.setattr(analysis.yf, "Ticker", _StaggeredStartYfTicker)

    prices, skipped = analysis.fetch_price_history(["AAA", "RECENT"], years=1)

    assert skipped == []
    # only the window both tickers actually traded in survives the join
    assert prices.shape[0] == 40
    assert prices.index.min() == pd.Timestamp("2023-01-21")


class _GappyYfTicker:
    """AAA trades every day; GAPPY is missing one date in the middle (e.g. a trading halt)."""

    def __init__(self, symbol: str):
        self.symbol = symbol

    def history(self, period: str, auto_adjust: bool) -> pd.DataFrame:
        dates = pd.date_range("2023-01-01", periods=60, freq="D", tz="UTC")
        if self.symbol == "GAPPY":
            dates = dates.delete(30)
            return pd.DataFrame({"Close": 50.0 + np.arange(59, dtype=float)}, index=dates)
        return pd.DataFrame({"Close": 100.0 + np.arange(60, dtype=float)}, index=dates)


def test_fetch_price_history_drops_only_the_missing_date_not_the_whole_ticker(monkeypatch):
    monkeypatch.setattr(analysis.yf, "Ticker", _GappyYfTicker)

    prices, skipped = analysis.fetch_price_history(["AAA", "GAPPY"], years=1)

    assert skipped == []
    assert list(prices.columns) == ["AAA", "GAPPY"]
    assert prices.shape[0] == 59  # the one date GAPPY is missing gets dropped for both

    # alignment shouldn't leave any gaps for correlation_matrix to choke on
    returns = analysis.compute_returns(prices)
    corr = analysis.correlation_matrix(returns)
    assert not corr.isna().any().any()
