from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services import backtest


# compute_beta

def test_compute_beta_hand_computed():
    # Portfolio moves exactly 2x the benchmark on every day -> beta == 2.0
    # regardless of the benchmark's own variance (cov(2X, X) / var(X) = 2).
    benchmark = np.array([0.01, -0.01, 0.02, -0.02])
    portfolio = benchmark * 2

    assert backtest.compute_beta(portfolio, benchmark) == pytest.approx(2.0)


def test_compute_beta_zero_variance_benchmark_is_guarded():
    benchmark = np.array([0.01, 0.01, 0.01, 0.01])  # zero variance
    portfolio = np.array([0.02, -0.01, 0.03, 0.0])

    assert backtest.compute_beta(portfolio, benchmark) == 0.0


def test_compute_beta_uncorrelated_series_is_near_zero():
    rng = np.random.default_rng(seed=11)
    n = 5000
    benchmark = rng.normal(0, 0.01, n)
    portfolio = rng.normal(0, 0.01, n)  # independent of benchmark by construction

    assert backtest.compute_beta(portfolio, benchmark) == pytest.approx(0.0, abs=0.05)


# compute_alpha

def test_compute_alpha_hand_computed():
    # CAPM expects ~0.112 return here; actual is 0.15, so alpha should be ~0.038
    alpha = backtest.compute_alpha(
        portfolio_annual_return=0.15, benchmark_annual_return=0.10, beta=1.2, risk_free_rate=0.04
    )
    assert alpha == pytest.approx(0.038)


def test_compute_alpha_zero_beta_means_alpha_is_return_minus_risk_free():
    # beta=0 -> expected = risk_free_rate exactly, so alpha = actual - rf
    alpha = backtest.compute_alpha(
        portfolio_annual_return=0.10, benchmark_annual_return=0.20, beta=0.0, risk_free_rate=0.04
    )
    assert alpha == pytest.approx(0.06)


def test_compute_alpha_matching_capm_exactly_gives_zero_alpha():
    beta = 0.8
    benchmark_return = 0.12
    risk_free = 0.04
    portfolio_return = risk_free + beta * (benchmark_return - risk_free)  # exactly what CAPM predicts

    alpha = backtest.compute_alpha(portfolio_return, benchmark_return, beta, risk_free)

    assert alpha == pytest.approx(0.0, abs=1e-9)


# max_drawdown

def test_max_drawdown_hand_computed():
    # peak of 1.2, trough of 0.9 -> 25% drawdown
    values = [1.0, 1.2, 0.9, 1.1]
    assert backtest.max_drawdown(values) == pytest.approx(0.25)


def test_max_drawdown_monotonic_increase_is_zero():
    assert backtest.max_drawdown([1.0, 1.1, 1.2, 1.5]) == pytest.approx(0.0)


def test_max_drawdown_uses_the_worst_of_multiple_dips():
    # first dip is a shallow 5%; second is the real one, ~46%
    values = [1.0, 0.95, 1.3, 0.7, 1.0]
    assert backtest.max_drawdown(values) == pytest.approx(0.4615384615, rel=1e-6)


# run_backtest (integration-style: yfinance mocked out)

class _FakeYfTicker:
    def __init__(self, symbol: str):
        self.symbol = symbol

    def history(self, start: str, end: str, auto_adjust: bool) -> pd.DataFrame:
        if self.symbol == "DEAD":
            return pd.DataFrame()  # simulates an unresolvable ticker

        dates = pd.date_range(start, periods=120, freq="D", tz="UTC")
        rng = np.random.default_rng(seed=hash(self.symbol) % (2**32))
        # SPY drifts gently; everything else drifts a bit faster with more
        # noise, so beta/alpha come out as something other than exactly 1/0.
        if self.symbol == "SPY":
            daily = rng.normal(0.0003, 0.008, len(dates))
        else:
            daily = rng.normal(0.0006, 0.014, len(dates))
        prices = 100 * np.cumprod(1 + daily)
        return pd.DataFrame({"Close": prices}, index=dates)


def test_run_backtest_shape_and_invariants(monkeypatch):
    monkeypatch.setattr(backtest.yf, "Ticker", _FakeYfTicker)
    backtest.PRICE_HISTORY_CACHE.clear()

    result = backtest.run_backtest(
        tickers=["AAA", "BBB"],
        weights={"AAA": 0.6, "BBB": 0.4},
        start="2020-01-01",
        end="2020-06-01",
    )

    assert len(result.dates) == len(result.portfolio_path) == len(result.benchmark_path)
    assert result.portfolio_path[0] == pytest.approx(1.0)
    assert result.benchmark_path[0] == pytest.approx(1.0)
    assert result.portfolio_total_return == pytest.approx(result.portfolio_path[-1] - 1.0)
    assert result.portfolio_max_drawdown >= 0
    assert result.benchmark_max_drawdown >= 0
    assert result.skipped_tickers == []


def test_run_backtest_skips_unresolvable_holding_and_reweights(monkeypatch):
    monkeypatch.setattr(backtest.yf, "Ticker", _FakeYfTicker)
    backtest.PRICE_HISTORY_CACHE.clear()

    result = backtest.run_backtest(
        tickers=["AAA", "DEAD"],
        weights={"AAA": 0.5, "DEAD": 0.5},
        start="2020-01-01",
        end="2020-06-01",
    )

    assert result.skipped_tickers == ["DEAD"]
    # AAA alone should still produce a full, valid value path (its weight
    # gets renormalized to 1.0 once DEAD drops out).
    assert len(result.portfolio_path) > 1


def test_run_backtest_raises_when_benchmark_itself_is_unusable(monkeypatch):
    monkeypatch.setattr(backtest.yf, "Ticker", _FakeYfTicker)
    backtest.PRICE_HISTORY_CACHE.clear()

    with pytest.raises(backtest.InsufficientDataError):
        backtest.run_backtest(
            tickers=["AAA"],
            weights={"AAA": 1.0},
            start="2020-01-01",
            end="2020-06-01",
            benchmark_ticker="DEAD",
        )
