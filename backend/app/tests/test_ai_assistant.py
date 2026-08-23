from __future__ import annotations

import pytest

from app.services import ai_assistant, classification


# compute_signals

def test_compute_signals_flags_single_holding_concentration():
    signals = ai_assistant.compute_signals(
        weights={"AAPL": 0.7, "MSFT": 0.3},
        portfolio_volatility=0.15,
        sector_breakdown={},
        correlation_tickers=["AAPL", "MSFT"],
        correlation_matrix=[[1.0, 0.2], [0.2, 1.0]],
    )
    assert any("AAPL" in s.message and s.severity == "warning" for s in signals)


def test_compute_signals_does_not_flag_holding_under_threshold():
    signals = ai_assistant.compute_signals(
        weights={"AAPL": 0.15, "MSFT": 0.15, "GOOGL": 0.15, "JNJ": 0.15},
        portfolio_volatility=0.15,
        sector_breakdown={},
        correlation_tickers=[],
        correlation_matrix=[],
    )
    assert not any("AAPL" in s.message for s in signals)


def test_compute_signals_flags_sector_concentration():
    signals = ai_assistant.compute_signals(
        weights={"AAPL": 0.5, "MSFT": 0.5},
        portfolio_volatility=0.15,
        sector_breakdown={"Technology": 0.9, "Other": 0.1},
        correlation_tickers=[],
        correlation_matrix=[],
    )
    assert any("Technology" in s.message for s in signals)


def test_compute_signals_flags_high_correlation_between_meaningfully_weighted_holdings():
    signals = ai_assistant.compute_signals(
        weights={"AAPL": 0.5, "MSFT": 0.5},
        portfolio_volatility=0.15,
        sector_breakdown={},
        correlation_tickers=["AAPL", "MSFT"],
        correlation_matrix=[[1.0, 0.95], [0.95, 1.0]],
    )
    assert any("AAPL" in s.message and "MSFT" in s.message for s in signals)


def test_compute_signals_ignores_high_correlation_of_tiny_holdings():
    # both holdings under the 5% weight floor, shouldn't trigger even with high correlation
    signals = ai_assistant.compute_signals(
        weights={"AAPL": 0.02, "MSFT": 0.02, "OTHER": 0.96},
        portfolio_volatility=0.15,
        sector_breakdown={},
        correlation_tickers=["AAPL", "MSFT"],
        correlation_matrix=[[1.0, 0.95], [0.95, 1.0]],
    )
    assert not any("AAPL" in s.message and "MSFT" in s.message for s in signals)


def test_compute_signals_flags_high_volatility():
    signals = ai_assistant.compute_signals(
        weights={"AAPL": 1.0},
        portfolio_volatility=0.45,
        sector_breakdown={},
        correlation_tickers=[],
        correlation_matrix=[],
    )
    assert any("volatility" in s.message.lower() for s in signals)


def test_compute_signals_returns_reassuring_message_when_nothing_is_flagged():
    signals = ai_assistant.compute_signals(
        weights={"AAPL": 0.19, "MSFT": 0.19, "GOOGL": 0.19, "JNJ": 0.19, "V": 0.19},
        portfolio_volatility=0.12,
        sector_breakdown={"Technology": 0.5, "Healthcare": 0.5},
        correlation_tickers=["AAPL", "MSFT"],
        correlation_matrix=[[1.0, 0.1], [0.1, 1.0]],
    )
    assert len(signals) == 1
    assert signals[0].severity == "info"


# generate_insights (fallback path, no LLM)

def test_generate_insights_falls_back_to_rule_based_without_api_key(monkeypatch):
    monkeypatch.setattr(ai_assistant, "is_configured", lambda: False)

    result = ai_assistant.generate_insights(
        weights={"AAPL": 0.7, "MSFT": 0.3},
        portfolio_return=0.12,
        portfolio_volatility=0.20,
        sharpe_ratio=0.4,
        sector_breakdown={},
        correlation_tickers=["AAPL", "MSFT"],
        correlation_matrix=[[1.0, 0.3], [0.3, 1.0]],
    )

    assert result.source == "rule_based"
    assert any("AAPL" in line for line in result.insights)
    assert result.insights[-1] == ai_assistant.DISCLAIMER


def test_generate_insights_falls_back_when_llm_call_fails(monkeypatch):
    monkeypatch.setattr(ai_assistant, "is_configured", lambda: True)
    monkeypatch.setattr(ai_assistant, "complete_chat", lambda *a, **k: None)

    result = ai_assistant.generate_insights(
        weights={"AAPL": 1.0},
        portfolio_return=0.10,
        portfolio_volatility=0.15,
        sharpe_ratio=0.4,
        sector_breakdown={},
        correlation_tickers=[],
        correlation_matrix=[],
    )

    assert result.source == "rule_based"


def test_generate_insights_uses_llm_output_when_available(monkeypatch):
    monkeypatch.setattr(ai_assistant, "is_configured", lambda: True)
    monkeypatch.setattr(ai_assistant, "complete_chat", lambda *a, **k: "- First point.\n- Second point.")

    result = ai_assistant.generate_insights(
        weights={"AAPL": 1.0},
        portfolio_return=0.10,
        portfolio_volatility=0.15,
        sharpe_ratio=0.4,
        sector_breakdown={},
        correlation_tickers=[],
        correlation_matrix=[],
    )

    assert result.source == "llm"
    assert "First point." in result.insights
    assert result.insights[-1] == ai_assistant.DISCLAIMER


# suggested_allocation

def test_suggested_allocation_balanced_is_equal_weight():
    weights, _ = ai_assistant.suggested_allocation(
        [("AAPL", 0.15, 0.30), ("BND", 0.03, 0.05)], risk_profile="balanced"
    )
    assert weights["AAPL"] == pytest.approx(0.5)
    assert weights["BND"] == pytest.approx(0.5)


def test_suggested_allocation_conservative_favors_lower_volatility():
    # BND has much lower volatility than AAPL -> conservative should weight it higher.
    weights, _ = ai_assistant.suggested_allocation(
        [("AAPL", 0.15, 0.30), ("BND", 0.03, 0.05)], risk_profile="conservative"
    )
    assert weights["BND"] > weights["AAPL"]


def test_suggested_allocation_aggressive_favors_higher_return():
    weights, _ = ai_assistant.suggested_allocation(
        [("AAPL", 0.25, 0.30), ("BND", 0.03, 0.05)], risk_profile="aggressive"
    )
    assert weights["AAPL"] > weights["BND"]


def test_suggested_allocation_growth_favors_better_sharpe():
    # AAPL has a much better risk-adjusted return than BND here.
    weights, _ = ai_assistant.suggested_allocation(
        [("AAPL", 0.20, 0.15), ("BND", 0.02, 0.10)], risk_profile="growth"
    )
    assert weights["AAPL"] > weights["BND"]


def test_suggested_allocation_always_sums_to_one():
    for profile in ("conservative", "balanced", "growth", "aggressive"):
        weights, _ = ai_assistant.suggested_allocation(
            [("AAPL", 0.15, 0.30), ("MSFT", 0.12, 0.25), ("BND", 0.03, 0.05)], risk_profile=profile
        )
        assert sum(weights.values()) == pytest.approx(1.0)
        assert all(w >= 0 for w in weights.values())


# generate_ticker_research (fallback path, no LLM)

class _FakeYfTicker:
    def __init__(self, symbol: str):
        self.symbol = symbol

    def get_info(self) -> dict:
        return {
            "quoteType": "EQUITY",
            "sector": "Technology",
            "marketCap": 3_000_000_000_000,
            "longName": "Apple Inc.",
            "trailingPE": 35.2,
            "longBusinessSummary": "Apple designs consumer electronics.",
        }


def test_generate_ticker_research_falls_back_to_rule_based(monkeypatch):
    monkeypatch.setattr(ai_assistant, "is_configured", lambda: False)
    monkeypatch.setattr(ai_assistant.yf, "Ticker", _FakeYfTicker)
    monkeypatch.setattr(classification.yf, "Ticker", _FakeYfTicker)
    classification.COMPANY_INFO_CACHE.clear()

    result = ai_assistant.generate_ticker_research("AAPL")

    assert result.source == "rule_based"
    assert result.sector == "Technology"
    assert "Apple" in result.summary
    assert result.trailing_pe == pytest.approx(35.2)
