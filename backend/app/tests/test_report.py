from __future__ import annotations

import csv
import io

from app.models import (
    AnalyzeResponse,
    BreakdownSlice,
    CorrelationMatrix,
    EfficientFrontier,
    FactorBreakdown,
    FrontierPoint,
    HoldingStats,
    MonteCarloBand,
    MonteCarloResult,
    OptimalPortfolio,
    PortfolioStats,
)
from app.services.report import generate_csv, generate_pdf


def _sample_analysis() -> AnalyzeResponse:
    return AnalyzeResponse(
        holdings=[
            HoldingStats(ticker="AAPL", weight=0.6, annual_return=0.18, annual_volatility=0.28, sharpe_ratio=0.5),
            HoldingStats(ticker="BND", weight=0.4, annual_return=0.03, annual_volatility=0.06, sharpe_ratio=-0.17),
        ],
        portfolio=PortfolioStats(annual_return=0.12, annual_volatility=0.18, sharpe_ratio=0.44, value_at_risk_95=0.15),
        correlation=CorrelationMatrix(tickers=["AAPL", "BND"], matrix=[[1.0, -0.1], [-0.1, 1.0]]),
        efficient_frontier=EfficientFrontier(
            points=[FrontierPoint(annual_return=0.03, annual_volatility=0.06), FrontierPoint(annual_return=0.18, annual_volatility=0.28)],
            user_portfolio=FrontierPoint(annual_return=0.12, annual_volatility=0.18),
            max_sharpe=OptimalPortfolio(annual_return=0.10, annual_volatility=0.12, sharpe_ratio=0.5, weights={"AAPL": 0.5, "BND": 0.5}),
            min_volatility=OptimalPortfolio(annual_return=0.05, annual_volatility=0.07, sharpe_ratio=0.14, weights={"AAPL": 0.2, "BND": 0.8}),
        ),
        monte_carlo=MonteCarloResult(
            starting_value=1.0,
            bands=[MonteCarloBand(day=0, p5=1.0, p25=1.0, p50=1.0, p75=1.0, p95=1.0)],
            value_at_risk_95=0.15,
        ),
        factor_breakdown=FactorBreakdown(
            sector=[BreakdownSlice(label="Technology", weight=0.6), BreakdownSlice(label="Fixed Income", weight=0.4)],
            market_cap=[BreakdownSlice(label="Mega Cap", weight=0.6), BreakdownSlice(label="ETF / Fund", weight=0.4)],
            concentration_warnings=[],
        ),
        skipped_tickers=["ZZZBAD"],
        lookback_years=5,
    )


def test_generate_csv_contains_key_figures():
    csv_bytes = generate_csv(_sample_analysis())
    text = csv_bytes.decode("utf-8")

    rows = list(csv.reader(io.StringIO(text)))
    flat = [cell for row in rows for cell in row]

    assert "AAPL" in flat
    assert "BND" in flat
    assert "Technology" in flat


def test_generate_pdf_produces_a_valid_pdf_document():
    pdf_bytes = generate_pdf(_sample_analysis())
    assert pdf_bytes.startswith(b"%PDF")

# TODO: cover the ai_insights path for both formats once report.py settles down
