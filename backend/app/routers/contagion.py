"""Contagion / shock-diffusion simulation endpoint."""
from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from app.models import (
    ContagionSummary,
    GraphEdge,
    GraphNode,
    ShockSimulationRequest,
    ShockSimulationResponse,
)
from app.services.analysis import InsufficientDataError, compute_returns, fetch_price_history
from app.services.classification import fetch_profiles
from app.services.contagion import NodeImpact, build_portfolio_graph, generate_risk_summary, simulate_shock

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["contagion"])


@router.post("/simulate-shock", response_model=ShockSimulationResponse)
def simulate_shock_endpoint(request: ShockSimulationRequest) -> ShockSimulationResponse:
    tickers = [h.ticker for h in request.holdings]
    requested_weights = {h.ticker: h.weight for h in request.holdings}

    try:
        prices, skipped_tickers = fetch_price_history(tickers, request.lookback_years)
    except InsufficientDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    valid_tickers = list(prices.columns)
    if request.origin_ticker not in valid_tickers:
        raise HTTPException(
            status_code=422,
            detail=f"Couldn't resolve '{request.origin_ticker}' to price data, so a shock can't be simulated from it",
        )

    # same rescale rule as /analyze
    raw_weights = {t: requested_weights[t] for t in valid_tickers}
    total_weight = sum(raw_weights.values())
    if total_weight <= 0:
        raise HTTPException(status_code=422, detail="No valid holdings remain after removing unresolvable tickers")
    weights = {t: w / total_weight for t, w in raw_weights.items()}

    returns = compute_returns(prices)
    profiles = fetch_profiles(valid_tickers)
    sectors = {t: p.sector for t, p in profiles.items()}

    graph = build_portfolio_graph(valid_tickers, weights, returns, sectors)

    try:
        result = simulate_shock(graph, request.origin_ticker, request.shock_magnitude, request.decay_factor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    narrative, source = generate_risk_summary(result, graph, request.shock_magnitude)

    def to_graph_node(n: NodeImpact) -> GraphNode:
        data = graph.nodes[n.ticker]
        return GraphNode(
            ticker=n.ticker,
            weight=data["weight"],
            sector=data["sector"],
            annual_return=data["annual_return"],
            hop_distance=n.hop_distance,
            impact_score=n.impact_score,
            price_drawdown=n.price_drawdown,
            status=n.status,
        )

    return ShockSimulationResponse(
        nodes=[to_graph_node(n) for n in result.nodes],
        edges=[GraphEdge(source=e.source, target=e.target, correlation=e.correlation) for e in result.edges],
        summary=ContagionSummary(
            origin_ticker=request.origin_ticker,
            shock_magnitude=request.shock_magnitude,
            decay_factor=request.decay_factor,
            total_portfolio_drawdown=result.total_portfolio_drawdown,
            highest_risk_secondary=[to_graph_node(n) for n in result.highest_risk_secondary],
            risk_narrative=narrative,
            narrative_source=source,
        ),
        skipped_tickers=skipped_tickers,
    )
