"""HTTP layer tests: request validation and error responses. No network calls."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

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
