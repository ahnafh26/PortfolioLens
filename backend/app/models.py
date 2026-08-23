"""Request/response models for the API. Kept in one file so the frontend types stay in sync."""
from __future__ import annotations

import re
from collections.abc import Sequence
from datetime import date, datetime, timedelta
from typing import Annotated, Protocol

from pydantic import AfterValidator, BaseModel, Field, field_validator, model_validator

# real-world symbols look like AAPL, BRK.B, BF-B -- this also keeps ticker strings out of
# reach of CSV-formula-injection payloads (=, @, ...) and yfinance requests built from junk input
_TICKER_PATTERN = re.compile(r"^[A-Z0-9.\-]{1,10}$")

MAX_BACKTEST_YEARS = 20
_EARLIEST_BACKTEST_DATE = date(1970, 1, 1)


def _validate_ticker(v: str) -> str:
    upper = v.strip().upper()
    if not _TICKER_PATTERN.match(upper):
        raise ValueError(f"'{v}' is not a valid ticker symbol")
    return upper


# uppercases + validates on assignment, reused by every model with a ticker field
Ticker = Annotated[str, AfterValidator(_validate_ticker)]


class _WeightedHolding(Protocol):
    ticker: str
    weight: float


def _check_weights_sum_to_one_and_unique(holdings: Sequence[_WeightedHolding]) -> None:
    total = sum(h.weight for h in holdings)
    # small epsilon, frontend sends stuff like 0.3333 repeating
    if abs(total - 1.0) > 0.01:
        raise ValueError(f"Holding weights must sum to 1.0 (100%); received {total:.4f}")
    tickers = [h.ticker for h in holdings]
    if len(tickers) != len(set(tickers)):
        raise ValueError("Duplicate tickers are not allowed in a single portfolio")


class HoldingInput(BaseModel):
    ticker: Ticker = Field(..., min_length=1, max_length=10, description="Exchange ticker symbol, e.g. AAPL")
    weight: float = Field(..., gt=0, le=1, description="Fraction of the portfolio allocated to this holding, e.g. 0.25 for 25%")


class HoldingsRequestBase(BaseModel):
    """Shared holdings field + validation (sum to 1, no dupes) for analyze/backtest/rebalance."""

    holdings: list[HoldingInput] = Field(..., min_length=1, max_length=25)

    @field_validator("holdings")
    @classmethod
    def _weights_sum_to_one(cls, holdings: list[HoldingInput]) -> list[HoldingInput]:
        _check_weights_sum_to_one_and_unique(holdings)
        return holdings


class AnalyzeRequest(HoldingsRequestBase):
    lookback_years: int = Field(default=5, ge=1, le=20, description="How many years of daily price history to pull")


class HoldingStats(BaseModel):
    """Per-holding stats, independent of portfolio interactions."""

    ticker: str
    weight: float
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float


class PortfolioStats(BaseModel):
    """Portfolio-level stats, accounts for diversification."""

    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    value_at_risk_95: float = Field(..., description="1-year 95% VaR, expressed as a fraction of portfolio value (e.g. 0.18 = a 5% chance of losing 18%+ of value over the next year)")


class CorrelationMatrix(BaseModel):
    tickers: list[str] = Field(..., max_length=25)
    matrix: list[list[float]] = Field(..., max_length=25, description="Row-major matrix; matrix[i][j] is the correlation between tickers[i] and tickers[j]")

    @field_validator("matrix")
    @classmethod
    def _rows_bounded(cls, v: list[list[float]]) -> list[list[float]]:
        # AnalyzeResponse.correlation is client-supplied at export time (see ExportRequest);
        # bound each row too, not just the row count, so a huge matrix can't sneak in sideways
        if any(len(row) > 25 for row in v):
            raise ValueError("Correlation matrix rows must have at most 25 entries")
        return v


class FrontierPoint(BaseModel):
    annual_return: float
    annual_volatility: float


class OptimalPortfolio(BaseModel):
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    weights: dict[str, float]


class EfficientFrontier(BaseModel):
    points: list[FrontierPoint] = Field(..., max_length=200)
    user_portfolio: FrontierPoint
    max_sharpe: OptimalPortfolio
    min_volatility: OptimalPortfolio


class MonteCarloBand(BaseModel):
    """One slice of the fan chart."""

    day: int
    p5: float
    p25: float
    p50: float
    p75: float
    p95: float


class MonteCarloResult(BaseModel):
    starting_value: float = Field(..., description="Normalized starting portfolio value (always 1.0 == 100%)")
    bands: list[MonteCarloBand] = Field(..., max_length=200)
    value_at_risk_95: float = Field(..., description="1-year 95% VaR as a fraction of starting value")


class BreakdownSlice(BaseModel):
    label: str = Field(..., max_length=100)
    weight: float


class FactorBreakdown(BaseModel):
    """Sector/cap composition, plus concentration warnings (>50% in one bucket)."""

    sector: list[BreakdownSlice] = Field(..., max_length=50)
    market_cap: list[BreakdownSlice] = Field(..., max_length=50)
    concentration_warnings: list[BreakdownSlice] = Field(..., max_length=50)


class AnalyzeResponse(BaseModel):
    holdings: list[HoldingStats] = Field(..., max_length=25)
    portfolio: PortfolioStats
    correlation: CorrelationMatrix
    efficient_frontier: EfficientFrontier
    monte_carlo: MonteCarloResult
    factor_breakdown: FactorBreakdown
    skipped_tickers: list[str] = Field(default_factory=list, max_length=25, description="Tickers that were requested but couldn't be resolved to price data")
    lookback_years: int


class TickerSearchResult(BaseModel):
    symbol: str
    name: str
    exchange: str


class TickerSearchResponse(BaseModel):
    results: list[TickerSearchResult]


class BacktestRequest(HoldingsRequestBase):
    period: str = Field(
        ...,
        description='One of "gfc_2008", "covid_2020", "rate_hikes_2022", or "custom" '
        "(custom requires start_date/end_date).",
    )
    start_date: str | None = Field(default=None, description="YYYY-MM-DD, required when period=custom")
    end_date: str | None = Field(default=None, description="YYYY-MM-DD, required when period=custom")

    @field_validator("period")
    @classmethod
    def _valid_period(cls, v: str) -> str:
        if v not in ("gfc_2008", "covid_2020", "rate_hikes_2022", "custom"):
            raise ValueError(f"Unknown period '{v}'")
        return v

    @field_validator("start_date", "end_date")
    @classmethod
    def _valid_date_format(cls, v: str | None) -> str | None:
        if v is None:
            return v
        try:
            parsed = datetime.strptime(v, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError(f"'{v}' is not a valid YYYY-MM-DD date") from exc
        if parsed < _EARLIEST_BACKTEST_DATE or parsed > date.today():
            raise ValueError(f"'{v}' is outside the supported date range ({_EARLIEST_BACKTEST_DATE} to today)")
        return v

    @model_validator(mode="after")
    def _custom_period_requires_dates(self) -> "BacktestRequest":
        if self.period != "custom":
            return self
        if not self.start_date or not self.end_date:
            raise ValueError("start_date and end_date are required when period is 'custom'")

        start = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        end = datetime.strptime(self.end_date, "%Y-%m-%d").date()
        if start >= end:
            raise ValueError("start_date must be before end_date")
        if end - start > timedelta(days=365 * MAX_BACKTEST_YEARS):
            raise ValueError(f"Custom backtest range can't exceed {MAX_BACKTEST_YEARS} years")
        return self


class BacktestResponse(BaseModel):
    period_label: str
    start_date: str
    end_date: str
    dates: list[str]
    portfolio_path: list[float] = Field(..., description="Portfolio value, normalized to 1.0 at the start of the period")
    benchmark_path: list[float] = Field(..., description="SPY value, normalized to 1.0 at the start of the period")
    portfolio_total_return: float
    benchmark_total_return: float
    portfolio_max_drawdown: float
    benchmark_max_drawdown: float
    alpha: float = Field(..., description="Jensen's alpha: annualized return in excess of what beta alone would predict")
    beta: float
    skipped_tickers: list[str] = Field(default_factory=list)


class CurrentHolding(BaseModel):
    ticker: Ticker = Field(..., min_length=1, max_length=10)
    weight: float = Field(..., gt=0, le=1, description="Target weight, e.g. 0.25 for 25%")
    current_value: float = Field(default=0.0, ge=0, description="Current dollar value already held in this ticker (0 if starting fresh)")


class RebalanceRequest(BaseModel):
    holdings: list[CurrentHolding] = Field(..., min_length=1, max_length=25)
    total_value: float = Field(..., gt=0, description="Target total portfolio value in dollars")

    @field_validator("holdings")
    @classmethod
    def _weights_sum_to_one(cls, holdings: list[CurrentHolding]) -> list[CurrentHolding]:
        _check_weights_sum_to_one_and_unique(holdings)
        return holdings


class RebalanceOrder(BaseModel):
    ticker: str
    action: str = Field(..., description='"buy" or "sell"')
    shares: float
    price: float
    dollar_amount: float
    current_value: float
    target_value: float


class RebalanceResponse(BaseModel):
    orders: list[RebalanceOrder]
    leftover_cash: float = Field(..., description="Cash that can't buy a whole additional share of anything, if fractional shares are disallowed")
    total_value: float
    skipped_tickers: list[str] = Field(default_factory=list, description="Tickers whose current price couldn't be fetched")


RISK_PROFILES = ("conservative", "balanced", "growth", "aggressive")


class AIInsightsRequest(BaseModel):
    """Takes already-computed AnalyzeResponse pieces instead of re-deriving them."""

    holdings: list[HoldingInput] = Field(..., min_length=1, max_length=25)
    annual_return: float
    annual_volatility: float
    sharpe_ratio: float
    sector_breakdown: list[BreakdownSlice]
    correlation: CorrelationMatrix


class AIInsightsResponse(BaseModel):
    insights: list[str]
    source: str = Field(..., description='"llm" if OpenRouter generated the prose, "rule_based" otherwise')


class TickerResearchResponse(BaseModel):
    ticker: str
    name: str
    sector: str
    market_cap_bucket: str
    trailing_pe: float | None
    summary: str
    source: str = Field(..., description='"llm" if OpenRouter generated the summary, "rule_based" otherwise')


class HoldingPerformance(BaseModel):
    ticker: Ticker = Field(..., min_length=1, max_length=10)
    annual_return: float
    annual_volatility: float


class SuggestedAllocationRequest(BaseModel):
    holdings: list[HoldingPerformance] = Field(..., min_length=1, max_length=25)
    risk_profile: str

    @field_validator("risk_profile")
    @classmethod
    def _valid_risk_profile(cls, v: str) -> str:
        if v not in RISK_PROFILES:
            raise ValueError(f"risk_profile must be one of {RISK_PROFILES}")
        return v


class SuggestedAllocationResponse(BaseModel):
    risk_profile: str
    weights: dict[str, float]
    rationale: str


class ExportRequest(BaseModel):
    """Re-formats an already-computed analysis, doesn't re-run one."""

    analysis: AnalyzeResponse
    ai_insights: list[str] | None = Field(default=None, max_length=50)

    @field_validator("ai_insights")
    @classmethod
    def _insight_lines_bounded(cls, v: list[str] | None) -> list[str] | None:
        if v is not None and any(len(line) > 2000 for line in v):
            raise ValueError("Each AI insight line must be at most 2000 characters")
        return v


class ShockSimulationRequest(HoldingsRequestBase):
    origin_ticker: Ticker = Field(..., min_length=1, max_length=10, description="Ticker where the price shock originates, e.g. AAPL")
    shock_magnitude: float = Field(
        ..., lt=0, ge=-1, description="Percentage price drop at the origin, expressed as a negative fraction, e.g. -0.15 for -15%"
    )
    decay_factor: float = Field(
        default=0.65, gt=0, le=1, description="How much the shock's impact shrinks per graph hop away from the origin"
    )
    lookback_years: int = Field(default=3, ge=1, le=20, description="How many years of daily price history to use for the correlation graph")

    @model_validator(mode="after")
    def _origin_is_a_holding(self) -> "ShockSimulationRequest":
        if self.origin_ticker not in {h.ticker for h in self.holdings}:
            raise ValueError(f"origin_ticker '{self.origin_ticker}' must be one of the portfolio holdings")
        return self


class GraphNode(BaseModel):
    ticker: str
    weight: float
    sector: str
    annual_return: float
    hop_distance: int | None = Field(..., description="Shortest number of graph hops from the shock origin; null if unreached")
    impact_score: float = Field(..., description="Infected Impact Score from 0 (unaffected) to 1 (the origin itself)")
    price_drawdown: float = Field(..., description="Estimated price change as a fraction, e.g. -0.06 for -6%")
    status: str = Field(..., description='"healthy" | "at_risk" | "critical"')


class GraphEdge(BaseModel):
    source: str
    target: str
    correlation: float


class ContagionSummary(BaseModel):
    origin_ticker: str
    shock_magnitude: float
    decay_factor: float
    total_portfolio_drawdown: float
    highest_risk_secondary: list[GraphNode]
    risk_narrative: str
    narrative_source: str = Field(..., description='"llm" if OpenRouter generated the summary, "rule_based" otherwise')


class ShockSimulationResponse(BaseModel):
    nodes: list[GraphNode]
    edges: list[GraphEdge]
    summary: ContagionSummary
    skipped_tickers: list[str] = Field(default_factory=list, description="Tickers that were requested but couldn't be resolved to price data")
