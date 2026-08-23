"""Tests for contagion.py. Hand-built returns DataFrame so expected correlations are known upfront."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from app.services import contagion


def _returns_fixture() -> pd.DataFrame:
    # A: factor1 only. C: factor2 only. B: both, so B-A and B-C correlate (~0.66) but A-C doesn't (~0).
    # only path from A to C is via B.
    rng = np.random.default_rng(seed=42)
    n = 500
    factor1 = rng.normal(0, 1, n)
    factor2 = rng.normal(0, 1, n)
    noise = rng.normal(0, 0.3, (n, 3))
    a = factor1 + noise[:, 0]
    b = factor1 + factor2 + noise[:, 1]
    c = factor2 + noise[:, 2]
    return pd.DataFrame({"A": a, "B": b, "C": c})


def _weights() -> dict[str, float]:
    return {"A": 0.5, "B": 0.3, "C": 0.2}


def _sectors() -> dict[str, str]:
    return {"A": "Technology", "B": "Technology", "C": "Healthcare"}


# build_portfolio_graph

def test_build_portfolio_graph_only_draws_edges_above_threshold():
    returns = _returns_fixture()
    graph = contagion.build_portfolio_graph(["A", "B", "C"], _weights(), returns, _sectors())

    assert set(graph.nodes) == {"A", "B", "C"}
    assert graph.has_edge("A", "B")
    assert graph.has_edge("B", "A")
    # A and C constructed to be uncorrelated, no direct edge
    assert not graph.has_edge("A", "C")
    assert not graph.has_edge("C", "A")


def test_build_portfolio_graph_node_metadata():
    returns = _returns_fixture()
    graph = contagion.build_portfolio_graph(["A", "B", "C"], _weights(), returns, _sectors())

    assert graph.nodes["A"]["weight"] == pytest.approx(0.5)
    assert graph.nodes["A"]["sector"] == "Technology"
    assert graph.nodes["C"]["sector"] == "Healthcare"


# simulate_shock

def test_simulate_shock_origin_has_full_impact():
    returns = _returns_fixture()
    graph = contagion.build_portfolio_graph(["A", "B", "C"], _weights(), returns, _sectors())
    result = contagion.simulate_shock(graph, "A", shock_magnitude=-0.20, decay_factor=0.65)

    origin = next(n for n in result.nodes if n.ticker == "A")
    assert origin.hop_distance == 0
    assert origin.impact_score == pytest.approx(1.0)
    assert origin.price_drawdown == pytest.approx(-0.20)
    assert origin.status == contagion.STATUS_CRITICAL


def test_simulate_shock_unreachable_node_is_healthy_and_unaffected():
    # D is isolated: no edges to anything (weight 0 keeps total_drawdown math simple).
    returns = _returns_fixture()
    graph = contagion.build_portfolio_graph(["A", "B", "C"], _weights(), returns, _sectors())
    graph.add_node("D", weight=0.0, sector="Energy", annual_return=0.0)

    result = contagion.simulate_shock(graph, "A", shock_magnitude=-0.20, decay_factor=0.65)

    d = next(n for n in result.nodes if n.ticker == "D")
    assert d.hop_distance is None
    assert d.impact_score == 0.0
    assert d.price_drawdown == 0.0
    assert d.status == contagion.STATUS_HEALTHY


def test_simulate_shock_highest_risk_secondary_excludes_origin_and_is_sorted():
    returns = _returns_fixture()
    graph = contagion.build_portfolio_graph(["A", "B", "C"], _weights(), returns, _sectors())
    result = contagion.simulate_shock(graph, "A", shock_magnitude=-0.20, decay_factor=0.65)

    secondary_tickers = [n.ticker for n in result.highest_risk_secondary]
    assert "A" not in secondary_tickers
    assert secondary_tickers == ["B", "C"]  # B (1 hop) more impacted than C (2 hops)
    scores = [n.impact_score for n in result.highest_risk_secondary]
    assert scores == sorted(scores, reverse=True)


def test_simulate_shock_unknown_origin_raises():
    returns = _returns_fixture()
    graph = contagion.build_portfolio_graph(["A", "B", "C"], _weights(), returns, _sectors())
    with pytest.raises(ValueError):
        contagion.simulate_shock(graph, "ZZZZ", shock_magnitude=-0.20)


# generate_risk_summary (rule-based fallback, no API key in test env)

def test_generate_risk_summary_falls_back_to_rule_based(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    returns = _returns_fixture()
    graph = contagion.build_portfolio_graph(["A", "B", "C"], _weights(), returns, _sectors())
    result = contagion.simulate_shock(graph, "A", shock_magnitude=-0.20, decay_factor=0.65)

    narrative, source = contagion.generate_risk_summary(result, graph, shock_magnitude=-0.20)
    assert source == "rule_based"
    assert "A" in narrative
    assert "B" in narrative
