"""AI Assistant endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.models import (
    AIInsightsRequest,
    AIInsightsResponse,
    SuggestedAllocationRequest,
    SuggestedAllocationResponse,
    TickerResearchResponse,
)
from app.services.ai_assistant import generate_insights, generate_ticker_research, suggested_allocation

router = APIRouter(prefix="/api/ai", tags=["ai"])


@router.post("/insights", response_model=AIInsightsResponse)
def insights(request: AIInsightsRequest) -> AIInsightsResponse:
    weights = {h.ticker: h.weight for h in request.holdings}
    sector_breakdown = {s.label: s.weight for s in request.sector_breakdown}

    result = generate_insights(
        weights=weights,
        portfolio_return=request.annual_return,
        portfolio_volatility=request.annual_volatility,
        sharpe_ratio=request.sharpe_ratio,
        sector_breakdown=sector_breakdown,
        correlation_tickers=request.correlation.tickers,
        correlation_matrix=request.correlation.matrix,
    )
    return AIInsightsResponse(insights=result.insights, source=result.source)


@router.get("/research", response_model=TickerResearchResponse)
def research(ticker: str = Query(..., min_length=1, max_length=10)) -> TickerResearchResponse:
    ticker = ticker.strip().upper()
    result = generate_ticker_research(ticker)
    return TickerResearchResponse(
        ticker=result.ticker,
        name=result.name,
        sector=result.sector,
        market_cap_bucket=result.market_cap_bucket,
        trailing_pe=result.trailing_pe,
        summary=result.summary,
        source=result.source,
    )


@router.post("/suggested-allocation", response_model=SuggestedAllocationResponse)
def get_suggested_allocation(request: SuggestedAllocationRequest) -> SuggestedAllocationResponse:
    holdings = [(h.ticker, h.annual_return, h.annual_volatility) for h in request.holdings]
    weights, rationale = suggested_allocation(holdings, request.risk_profile)
    return SuggestedAllocationResponse(risk_profile=request.risk_profile, weights=weights, rationale=rationale)
