from __future__ import annotations

from app.services import classification


def test_classify_market_cap_tiers():
    assert classification.classify_market_cap(3_000_000_000_000, is_fund=False) == "Mega Cap"
    assert classification.classify_market_cap(50_000_000_000, is_fund=False) == "Large Cap"
    assert classification.classify_market_cap(5_000_000_000, is_fund=False) == "Mid Cap"
    assert classification.classify_market_cap(500_000_000, is_fund=False) == "Small Cap"
    assert classification.classify_market_cap(50_000_000, is_fund=False) == "Micro Cap"


def test_classify_market_cap_unknown_when_missing():
    assert classification.classify_market_cap(None, is_fund=False) == "Unknown"


def test_classify_market_cap_funds_get_their_own_bucket_regardless_of_assets():
    # fund AUM isn't a company market cap, even a huge ETF shouldn't be "Mega Cap"
    assert classification.classify_market_cap(500_000_000_000, is_fund=True) == "ETF / Fund"


class _FakeYfTicker:
    def __init__(self, symbol: str):
        self.symbol = symbol

    def get_info(self) -> dict:
        if self.symbol == "AAPL":
            return {"quoteType": "EQUITY", "sector": "Technology", "marketCap": 3_000_000_000_000, "longName": "Apple Inc."}
        if self.symbol == "SPY":
            return {"quoteType": "ETF", "category": "Large Blend", "longName": "SPDR S&P 500 ETF Trust"}
        if self.symbol == "BROKEN":
            raise RuntimeError("simulated network failure")
        return {}


def test_fetch_company_profile_equity(monkeypatch):
    monkeypatch.setattr(classification.yf, "Ticker", _FakeYfTicker)
    classification.COMPANY_INFO_CACHE.clear()

    profile = classification.fetch_company_profile("AAPL")

    assert profile.sector == "Technology"
    assert profile.market_cap_bucket == "Mega Cap"
    assert profile.is_fund is False
    assert profile.name == "Apple Inc."


def test_fetch_company_profile_fund_uses_category_not_sector(monkeypatch):
    monkeypatch.setattr(classification.yf, "Ticker", _FakeYfTicker)
    classification.COMPANY_INFO_CACHE.clear()

    profile = classification.fetch_company_profile("SPY")

    assert profile.sector == "Large Blend"
    assert profile.market_cap_bucket == "ETF / Fund"
    assert profile.is_fund is True


def test_fetch_company_profile_failure_degrades_to_unknown_instead_of_raising(monkeypatch):
    monkeypatch.setattr(classification.yf, "Ticker", _FakeYfTicker)
    classification.COMPANY_INFO_CACHE.clear()

    profile = classification.fetch_company_profile("BROKEN")

    assert profile.sector == "Unknown"
    assert profile.market_cap_bucket == "Unknown"


def test_breakdown_by_aggregates_weight_per_bucket():
    profiles = {
        "AAPL": classification.CompanyProfile("AAPL", "Apple", False, "Technology", "Mega Cap"),
        "MSFT": classification.CompanyProfile("MSFT", "Microsoft", False, "Technology", "Mega Cap"),
        "JNJ": classification.CompanyProfile("JNJ", "J&J", False, "Healthcare", "Large Cap"),
    }
    weights = {"AAPL": 0.4, "MSFT": 0.3, "JNJ": 0.3}

    sector = classification.breakdown_by(profiles, weights, "sector")

    assert sector["Technology"] == 0.7
    assert sector["Healthcare"] == 0.3


def test_concentration_flags_only_returns_buckets_over_threshold():
    breakdown = {"Technology": 0.7, "Healthcare": 0.3}

    flags = classification.concentration_flags(breakdown, threshold=0.5)

    assert flags == [("Technology", 0.7)]
