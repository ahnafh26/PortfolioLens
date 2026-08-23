"""Sector/market-cap classification, from yfinance fundamentals not OHLC prices."""
from __future__ import annotations

import logging
from dataclasses import dataclass

import yfinance as yf

from app.services.cache import COMPANY_INFO_CACHE, cached_call

logger = logging.getLogger(__name__)

# rough tier boundaries (USD), no official standard here
_MARKET_CAP_TIERS: list[tuple[float, str]] = [
    (200_000_000_000, "Mega Cap"),
    (10_000_000_000, "Large Cap"),
    (2_000_000_000, "Mid Cap"),
    (300_000_000, "Small Cap"),
]
_MICRO_CAP = "Micro Cap"
_FUND_BUCKET = "ETF / Fund"
_UNKNOWN = "Unknown"


@dataclass(frozen=True)
class CompanyProfile:
    symbol: str
    name: str
    is_fund: bool
    sector: str  # sector for equities, Morningstar category for funds, "Unknown" otherwise
    market_cap_bucket: str


def classify_market_cap(market_cap: float | None, is_fund: bool) -> str:
    """Funds get their own bucket, market cap isn't a coherent concept for a fund."""
    if is_fund:
        return _FUND_BUCKET
    if market_cap is None or market_cap <= 0:
        return _UNKNOWN
    for floor, label in _MARKET_CAP_TIERS:
        if market_cap >= floor:
            return label
    return _MICRO_CAP


@cached_call(COMPANY_INFO_CACHE, key_prefix="company_profile")
def fetch_company_profile(ticker: str) -> CompanyProfile:
    """Never raises, falls back to Unknown fields on failure."""
    try:
        info = yf.Ticker(ticker).get_info()
    except Exception as exc:
        logger.warning("Failed to fetch company info for %s: %s", ticker, exc)
        return CompanyProfile(symbol=ticker, name=ticker, is_fund=False, sector=_UNKNOWN, market_cap_bucket=_UNKNOWN)

    is_fund = info.get("quoteType") in ("ETF", "MUTUALFUND")
    sector = (info.get("category") if is_fund else info.get("sector")) or _UNKNOWN

    name = info.get("longName") or info.get("shortName") or ticker
    market_cap_bucket = classify_market_cap(info.get("marketCap"), is_fund)

    return CompanyProfile(symbol=ticker, name=name, is_fund=is_fund, sector=sector, market_cap_bucket=market_cap_bucket)


def fetch_profiles(tickers: list[str]) -> dict[str, CompanyProfile]:
    return {t: fetch_company_profile(t) for t in tickers}


def breakdown_by(profiles: dict[str, CompanyProfile], weights: dict[str, float], key: str) -> dict[str, float]:
    """Aggregate portfolio weight by key ("sector" or "market_cap_bucket")."""
    totals: dict[str, float] = {}
    for ticker, weight in weights.items():
        profile = profiles.get(ticker)
        bucket = getattr(profile, key) if profile else _UNKNOWN
        totals[bucket] = totals.get(bucket, 0.0) + weight
    return totals


def concentration_flags(breakdown: dict[str, float], threshold: float = 0.5) -> list[tuple[str, float]]:
    """(label, weight) pairs for buckets over threshold."""
    return sorted(
        ((label, weight) for label, weight in breakdown.items() if weight > threshold),
        key=lambda pair: pair[1],
        reverse=True,
    )
