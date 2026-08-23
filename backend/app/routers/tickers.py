"""Ticker search endpoint backing the frontend's Add Holding combobox."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.limiter import rate_limit
from app.models import TickerSearchResponse, TickerSearchResult
from app.services.ticker_index import load_ticker_index

router = APIRouter(prefix="/api/tickers", tags=["tickers"])

# load once at startup, not per-request
_index = load_ticker_index()


@router.get("/search", response_model=TickerSearchResponse, dependencies=[Depends(rate_limit("30/minute"))])
def search_tickers(q: str = Query(..., min_length=1, max_length=50, description="Symbol or company name fragment")) -> TickerSearchResponse:
    matches = _index.search(q, limit=50)
    return TickerSearchResponse(
        results=[TickerSearchResult(symbol=m.symbol, name=m.name, exchange=m.exchange) for m in matches]
    )
