"""Portfolio contagion graph + shock-diffusion sim. Holdings are nodes, correlated pairs get edges,
a shock at one node diffuses outward with decay per hop. Simplified heat-diffusion, not a real
econometric contagion model, just meant to be directionally useful.
"""
from __future__ import annotations

import logging
from collections import deque
from dataclasses import dataclass, field

import networkx as nx
import pandas as pd

from app.services.analysis import TRADING_DAYS_PER_YEAR, correlation_matrix
from app.services.llm_client import complete_chat, is_configured

logger = logging.getLogger(__name__)

# below this correlation, don't draw an edge (too noisy to call it a spillover path)
CORRELATION_EDGE_THRESHOLD = 0.35

DEFAULT_DECAY_FACTOR = 0.65

# drives frontend node coloring (green/yellow/red)
AT_RISK_IMPACT_THRESHOLD = 0.1
CRITICAL_IMPACT_THRESHOLD = 0.5

TOP_SECONDARY_COUNT = 5

STATUS_HEALTHY = "healthy"
STATUS_AT_RISK = "at_risk"
STATUS_CRITICAL = "critical"


def build_portfolio_graph(
    tickers: list[str],
    weights: dict[str, float],
    returns: pd.DataFrame,
    sectors: dict[str, str],
) -> nx.DiGraph:
    # directed graph so diffusion walks out along out-edges, even though correlation itself is symmetric
    graph: nx.DiGraph = nx.DiGraph()
    corr = correlation_matrix(returns)

    for ticker in tickers:
        ann_return = float(returns[ticker].mean()) * TRADING_DAYS_PER_YEAR
        graph.add_node(
            ticker,
            weight=weights.get(ticker, 0.0),
            sector=sectors.get(ticker, "Unknown"),
            annual_return=ann_return,
        )

    for i, t1 in enumerate(tickers):
        for t2 in tickers[i + 1 :]:
            c = float(corr.loc[t1, t2])
            if abs(c) > CORRELATION_EDGE_THRESHOLD:
                graph.add_edge(t1, t2, correlation=c)
                graph.add_edge(t2, t1, correlation=c)

    return graph


@dataclass(frozen=True)
class NodeImpact:
    ticker: str
    hop_distance: int | None  # None if unreached from the origin
    impact_score: float  # 0 (unaffected) .. 1 (origin) "Infected Impact Score"
    price_drawdown: float  # estimated price change as a fraction, e.g. -0.06
    status: str  # STATUS_HEALTHY | STATUS_AT_RISK | STATUS_CRITICAL


@dataclass(frozen=True)
class GraphEdgeResult:
    source: str
    target: str
    correlation: float


@dataclass
class ShockSimulationResult:
    origin_ticker: str
    nodes: list[NodeImpact] = field(default_factory=list)
    edges: list[GraphEdgeResult] = field(default_factory=list)
    total_portfolio_drawdown: float = 0.0
    highest_risk_secondary: list[NodeImpact] = field(default_factory=list)


def _status_for_impact(ticker: str, origin_ticker: str, impact_score: float) -> str:
    if ticker == origin_ticker or impact_score >= CRITICAL_IMPACT_THRESHOLD:
        return STATUS_CRITICAL
    if impact_score >= AT_RISK_IMPACT_THRESHOLD:
        return STATUS_AT_RISK
    return STATUS_HEALTHY


def simulate_shock(
    graph: nx.DiGraph,
    origin_ticker: str,
    shock_magnitude: float,
    decay_factor: float = DEFAULT_DECAY_FACTOR,
) -> ShockSimulationResult:
    """BFS propagation from origin_ticker. impact_score = decay_factor**hop * path_strength,
    where path_strength is the running product of edge correlations along the BFS path.
    """
    if origin_ticker not in graph:
        raise ValueError(f"'{origin_ticker}' is not a node in this portfolio's graph")

    hop_distance: dict[str, int] = {origin_ticker: 0}
    path_strength: dict[str, float] = {origin_ticker: 1.0}

    queue: deque[str] = deque([origin_ticker])
    while queue:
        current = queue.popleft()
        for neighbor in graph.successors(current):
            if neighbor in hop_distance:
                continue
            edge_weight = abs(graph[current][neighbor]["correlation"])
            hop_distance[neighbor] = hop_distance[current] + 1
            path_strength[neighbor] = path_strength[current] * edge_weight
            queue.append(neighbor)

    nodes: list[NodeImpact] = []
    for ticker in graph.nodes:
        if ticker not in hop_distance:
            nodes.append(NodeImpact(ticker, None, 0.0, 0.0, STATUS_HEALTHY))
            continue
        d = hop_distance[ticker]
        impact_score = (decay_factor**d) * path_strength[ticker]
        drawdown = shock_magnitude * impact_score
        nodes.append(NodeImpact(ticker, d, impact_score, drawdown, _status_for_impact(ticker, origin_ticker, impact_score)))

    total_drawdown = sum(graph.nodes[n.ticker]["weight"] * n.price_drawdown for n in nodes)

    secondary = sorted(
        (n for n in nodes if n.ticker != origin_ticker and n.hop_distance is not None),
        key=lambda n: n.impact_score,
        reverse=True,
    )[:TOP_SECONDARY_COUNT]

    edges = [GraphEdgeResult(u, v, data["correlation"]) for u, v, data in graph.edges(data=True)]

    return ShockSimulationResult(
        origin_ticker=origin_ticker,
        nodes=nodes,
        edges=edges,
        total_portfolio_drawdown=total_drawdown,
        highest_risk_secondary=secondary,
    )


def _fallback_narrative(result: ShockSimulationResult, graph: nx.DiGraph, shock_magnitude: float) -> str:
    top = result.highest_risk_secondary[:3]
    if not top:
        return (
            f"A {shock_magnitude:.0%} shock to {result.origin_ticker} doesn't propagate meaningfully -- "
            f"no other holdings are correlated with it above {CORRELATION_EDGE_THRESHOLD:.2f}."
        )

    parts = []
    for n in top:
        edge = graph.get_edge_data(result.origin_ticker, n.ticker)
        if edge is not None:
            parts.append(f"{n.ticker} (correlation {edge['correlation']:.2f}, est. {n.price_drawdown:+.1%})")
        else:
            parts.append(f"{n.ticker} (indirect path, est. {n.price_drawdown:+.1%})")

    return (
        f"A {shock_magnitude:.0%} shock to {result.origin_ticker} propagates most heavily to "
        f"{', '.join(parts)}. Estimated total portfolio drawdown: {result.total_portfolio_drawdown:+.1%}."
    )


def generate_risk_summary(
    result: ShockSimulationResult,
    graph: nx.DiGraph,
    shock_magnitude: float,
) -> tuple[str, str]:
    """LLM-narrated if configured, same rule-based/LLM fallback pattern as ai_assistant.py otherwise.

    Returns (narrative, source) where source is "llm" or "rule_based".
    """
    fallback = _fallback_narrative(result, graph, shock_magnitude)

    if not is_configured():
        return fallback, "rule_based"

    top = result.highest_risk_secondary[:5]
    if not top:
        return fallback, "rule_based"

    signals_line = "\n".join(
        f"- {n.ticker}: hop {n.hop_distance} from {result.origin_ticker}, impact score {n.impact_score:.2f}, "
        f"est. price change {n.price_drawdown:+.1%}, sector {graph.nodes[n.ticker]['sector']}"
        for n in top
    )
    prompt = (
        "You are a portfolio risk analyst writing a brief contagion-risk note for a retail investor's "
        "dashboard. A simulated price shock was applied to one holding and propagated across a "
        "correlation network to the rest of the portfolio. Use ONLY the computed data below -- do not "
        "invent numbers, holdings, or events not listed.\n\n"
        f"Origin holding: {result.origin_ticker}, shock magnitude {shock_magnitude:.0%}\n"
        f"Estimated total portfolio drawdown: {result.total_portfolio_drawdown:+.1%}\n"
        f"Most affected secondary holdings:\n{signals_line}\n\n"
        "Write 1-2 short sentences explaining why the shock propagated the way it did (reference the "
        "correlation/sector relationships above). Return only the sentences, no preamble."
    )

    reply = complete_chat([{"role": "user", "content": prompt}], max_tokens=200)
    if reply is None:
        return fallback, "rule_based"
    return reply.strip(), "llm"
