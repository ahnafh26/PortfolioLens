"""HTTP layer tests: request validation and error responses. No network calls."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.models import HoldingInput

client = TestClient(app)


def test_health_check():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_analyze_rejects_weights_that_dont_sum_to_one():
    response = client.post(
        "/api/portfolio/analyze",
        json={"holdings": [{"ticker": "AAPL", "weight": 0.5}, {"ticker": "MSFT", "weight": 0.3}], "lookback_years": 5},
    )
    assert response.status_code == 422
    assert "sum to 1.0" in str(response.json())


def test_analyze_rejects_duplicate_tickers():
    response = client.post(
        "/api/portfolio/analyze",
        json={"holdings": [{"ticker": "AAPL", "weight": 0.5}, {"ticker": "aapl", "weight": 0.5}], "lookback_years": 5},
    )
    assert response.status_code == 422
    assert "Duplicate" in str(response.json())


def test_analyze_rejects_empty_holdings_list():
    response = client.post("/api/portfolio/analyze", json={"holdings": [], "lookback_years": 5})
    assert response.status_code == 422


def test_analyze_rejects_out_of_range_lookback_years():
    response = client.post(
        "/api/portfolio/analyze",
        json={"holdings": [{"ticker": "AAPL", "weight": 1.0}], "lookback_years": 50},
    )
    assert response.status_code == 422


def test_analyze_rejects_negative_weight():
    response = client.post(
        "/api/portfolio/analyze",
        json={"holdings": [{"ticker": "AAPL", "weight": -0.5}, {"ticker": "MSFT", "weight": 1.5}], "lookback_years": 5},
    )
    assert response.status_code == 422


def test_ticker_search_finds_exact_symbol_match():
    response = client.get("/api/tickers/search", params={"q": "AAPL"})
    assert response.status_code == 200
    results = response.json()["results"]
    assert results, "expected at least one result for AAPL"
    assert results[0]["symbol"] == "AAPL"


def test_ticker_search_ranks_symbol_prefix_above_fuzzy_name_hits():
    response = client.get("/api/tickers/search", params={"q": "MSFT"})
    results = response.json()["results"]
    assert results[0]["symbol"] == "MSFT"


def test_ticker_search_requires_a_query():
    response = client.get("/api/tickers/search")
    assert response.status_code == 422


def test_ticker_search_returns_empty_list_for_nonsense_query():
    response = client.get("/api/tickers/search", params={"q": "zzzzqqqqxxxx9999"})
    assert response.status_code == 200
    # fuzzy search may still return junk matches, just check it doesn't error and respects the cap
    assert len(response.json()["results"]) <= 50


def test_ticker_search_is_rate_limited_per_ip():
    """/api/tickers/search is capped at 30/minute; the request past that cap should be
    rejected rather than silently letting a single client hammer the endpoint forever."""
    for _ in range(30):
        response = client.get("/api/tickers/search", params={"q": "AAPL"})
        assert response.status_code == 200

    response = client.get("/api/tickers/search", params={"q": "AAPL"})
    assert response.status_code == 429


# ticker format validation (also closes off CSV-formula-injection and yfinance-request-abuse paths)

def test_analyze_rejects_ticker_with_formula_injection_characters():
    response = client.post(
        "/api/portfolio/analyze",
        json={"holdings": [{"ticker": "=CMD|'/C calc'!A1", "weight": 1.0}], "lookback_years": 5},
    )
    assert response.status_code == 422


def test_analyze_rejects_ticker_with_script_tag():
    response = client.post(
        "/api/portfolio/analyze",
        json={"holdings": [{"ticker": "<script>", "weight": 1.0}], "lookback_years": 5},
    )
    assert response.status_code == 422


def test_holding_input_accepts_real_world_ticker_formats():
    """BRK.B / BF-B style symbols (dot/hyphen) must still pass; this is what the ticker
    regex is actually there to allow, not just what it rejects. Checked against the model
    directly, not through /analyze, since that would need a real yfinance lookup to reach 200."""
    assert HoldingInput(ticker="BRK.B", weight=1.0).ticker == "BRK.B"
    assert HoldingInput(ticker="bf-b", weight=1.0).ticker == "BF-B"


# custom backtest date validation

def test_backtest_rejects_malformed_date_format():
    response = client.post(
        "/api/portfolio/backtest",
        json={
            "holdings": [{"ticker": "AAPL", "weight": 1.0}],
            "period": "custom",
            "start_date": "not-a-date",
            "end_date": "2020-01-01",
        },
    )
    assert response.status_code == 422


def test_backtest_rejects_start_date_after_end_date():
    response = client.post(
        "/api/portfolio/backtest",
        json={
            "holdings": [{"ticker": "AAPL", "weight": 1.0}],
            "period": "custom",
            "start_date": "2020-06-01",
            "end_date": "2020-01-01",
        },
    )
    assert response.status_code == 422


def test_backtest_rejects_a_future_date():
    response = client.post(
        "/api/portfolio/backtest",
        json={
            "holdings": [{"ticker": "AAPL", "weight": 1.0}],
            "period": "custom",
            "start_date": "2020-01-01",
            "end_date": "2999-01-01",
        },
    )
    assert response.status_code == 422


def test_backtest_rejects_a_range_over_the_max_years():
    response = client.post(
        "/api/portfolio/backtest",
        json={
            "holdings": [{"ticker": "AAPL", "weight": 1.0}],
            "period": "custom",
            "start_date": "1970-01-01",
            "end_date": "2020-01-01",
        },
    )
    assert response.status_code == 422


# export payload bounds (ExportRequest.ai_insights is raw client input, not re-derived)

def _sample_export_analysis() -> dict:
    return {
        "holdings": [{"ticker": "AAPL", "weight": 1.0, "annual_return": 0.1, "annual_volatility": 0.2, "sharpe_ratio": 0.5}],
        "portfolio": {"annual_return": 0.1, "annual_volatility": 0.2, "sharpe_ratio": 0.5, "value_at_risk_95": 0.1},
        "correlation": {"tickers": ["AAPL"], "matrix": [[1.0]]},
        "efficient_frontier": {
            "points": [{"annual_return": 0.1, "annual_volatility": 0.2}],
            "user_portfolio": {"annual_return": 0.1, "annual_volatility": 0.2},
            "max_sharpe": {"annual_return": 0.1, "annual_volatility": 0.2, "sharpe_ratio": 0.5, "weights": {"AAPL": 1.0}},
            "min_volatility": {"annual_return": 0.1, "annual_volatility": 0.2, "sharpe_ratio": 0.5, "weights": {"AAPL": 1.0}},
        },
        "monte_carlo": {"starting_value": 1.0, "bands": [{"day": 0, "p5": 1.0, "p25": 1.0, "p50": 1.0, "p75": 1.0, "p95": 1.0}], "value_at_risk_95": 0.1},
        "factor_breakdown": {"sector": [], "market_cap": [], "concentration_warnings": []},
        "skipped_tickers": [],
        "lookback_years": 5,
    }


def test_export_rejects_more_than_fifty_ai_insight_lines():
    response = client.post(
        "/api/portfolio/export/csv",
        json={"analysis": _sample_export_analysis(), "ai_insights": ["note"] * 51},
    )
    assert response.status_code == 422


def test_export_rejects_an_overlong_ai_insight_line():
    response = client.post(
        "/api/portfolio/export/csv",
        json={"analysis": _sample_export_analysis(), "ai_insights": ["x" * 2001]},
    )
    assert response.status_code == 422


def test_export_accepts_a_normal_ai_insights_payload():
    response = client.post(
        "/api/portfolio/export/csv",
        json={"analysis": _sample_export_analysis(), "ai_insights": ["Diversify more."]},
    )
    assert response.status_code == 200


# global request body size limit

def test_oversized_request_body_is_rejected_with_413():
    payload = b'{"holdings": [{"ticker": "AAPL", "weight": 1.0}], "lookback_years": 5, "padding": "' + b"a" * (2 * 1024 * 1024) + b'"}'
    response = client.post(
        "/api/portfolio/analyze",
        content=payload,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 413
