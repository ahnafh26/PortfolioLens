"""Portfolio endpoints. Thin router, math lives in services/analysis.py."""
from __future__ import annotations

import logging

import numpy as np
from fastapi import APIRouter, Depends, HTTPException, Response

from app.limiter import limit_concurrent_analysis, rate_limit
from app.models import (
    AnalyzeRequest,
    AnalyzeResponse,
    BacktestRequest,
    BacktestResponse,
    BreakdownSlice,
    CorrelationMatrix,
    EfficientFrontier,
    ExportRequest,
    FactorBreakdown,
    FrontierPoint,
    HoldingStats,
    MonteCarloBand,
    MonteCarloResult as MonteCarloResponseModel,
    OptimalPortfolio,
    PortfolioStats,
    RebalanceOrder,
    RebalanceRequest,
    RebalanceResponse,
)
from app.services.analysis import (
    InsufficientDataError,
    annualize_return,
    annualize_volatility,
    compute_returns,
    correlation_matrix,
    efficient_frontier,
    fetch_price_history,
    monte_carlo_simulation,
    sharpe_ratio,
)
from app.services.backtest import STRESS_PERIODS, run_backtest
from app.services.classification import breakdown_by, concentration_flags, fetch_profiles
from app.services.rebalance import rebalance_portfolio
from app.services.report import generate_csv, generate_pdf

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


@router.post(
    "/analyze",
    response_model=AnalyzeResponse,
    # runs a full optimization sweep + 10k-path Monte Carlo per call
    dependencies=[Depends(rate_limit("10/minute")), Depends(limit_concurrent_analysis)],
)
def analyze_portfolio(request: AnalyzeRequest) -> AnalyzeResponse:
    tickers = [h.ticker for h in request.holdings]
    requested_weights = {h.ticker: h.weight for h in request.holdings}

    try:
        prices, skipped_tickers = fetch_price_history(tickers, request.lookback_years)
    except InsufficientDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    valid_tickers = list(prices.columns)
    if not valid_tickers:
        raise HTTPException(status_code=422, detail="None of the requested tickers could be resolved to price data")

    # dropped tickers mean remaining weights no longer sum to 1, rescale
    raw_weights = {t: requested_weights[t] for t in valid_tickers}
    total_weight = sum(raw_weights.values())
    if total_weight <= 0:
        raise HTTPException(status_code=422, detail="No valid holdings remain after removing unresolvable tickers")
    weights = {t: w / total_weight for t, w in raw_weights.items()}

    returns = compute_returns(prices)

    holding_stats: list[HoldingStats] = []
    for ticker in valid_tickers:
        daily = returns[ticker]
        ann_return = annualize_return(daily)
        ann_vol = annualize_volatility(daily)
        holding_stats.append(
            HoldingStats(
                ticker=ticker,
                weight=weights[ticker],
                annual_return=ann_return,
                annual_volatility=ann_vol,
                sharpe_ratio=sharpe_ratio(ann_return, ann_vol),
            )
        )

    # weighted sum of daily returns, not a weighted avg of annualized stats
    weight_vector = np.array([weights[t] for t in returns.columns])
    portfolio_daily_returns = returns.to_numpy() @ weight_vector
    portfolio_return = annualize_return(portfolio_daily_returns)
    portfolio_vol = annualize_volatility(portfolio_daily_returns)

    corr_df = correlation_matrix(returns)

    try:
        frontier = efficient_frontier(returns, n_portfolios=50)
    except RuntimeError as exc:
        raise HTTPException(status_code=500, detail=f"Portfolio optimization failed: {exc}") from exc

    mc = monte_carlo_simulation(returns, weights, years=10, n_simulations=10_000)

    # fundamentals lookups never fail the request, just skip the breakdown
    profiles = fetch_profiles(valid_tickers)
    sector_totals = breakdown_by(profiles, weights, "sector")
    market_cap_totals = breakdown_by(profiles, weights, "market_cap_bucket")
    factor_breakdown = FactorBreakdown(
        sector=[BreakdownSlice(label=k, weight=v) for k, v in sector_totals.items()],
        market_cap=[BreakdownSlice(label=k, weight=v) for k, v in market_cap_totals.items()],
        concentration_warnings=[
            BreakdownSlice(label=label, weight=weight) for label, weight in concentration_flags(sector_totals)
        ],
    )

    return AnalyzeResponse(
        holdings=holding_stats,
        portfolio=PortfolioStats(
            annual_return=portfolio_return,
            annual_volatility=portfolio_vol,
            sharpe_ratio=sharpe_ratio(portfolio_return, portfolio_vol),
            value_at_risk_95=mc.value_at_risk_95,
        ),
        correlation=CorrelationMatrix(tickers=list(corr_df.columns), matrix=corr_df.to_numpy().tolist()),
        efficient_frontier=EfficientFrontier(
            points=[FrontierPoint(annual_return=r, annual_volatility=v) for r, v in frontier.points],
            user_portfolio=FrontierPoint(annual_return=portfolio_return, annual_volatility=portfolio_vol),
            max_sharpe=OptimalPortfolio(
                annual_return=frontier.max_sharpe.annual_return,
                annual_volatility=frontier.max_sharpe.annual_volatility,
                sharpe_ratio=frontier.max_sharpe.sharpe_ratio,
                weights=frontier.max_sharpe.weights,
            ),
            min_volatility=OptimalPortfolio(
                annual_return=frontier.min_volatility.annual_return,
                annual_volatility=frontier.min_volatility.annual_volatility,
                sharpe_ratio=frontier.min_volatility.sharpe_ratio,
                weights=frontier.min_volatility.weights,
            ),
        ),
        monte_carlo=MonteCarloResponseModel(
            starting_value=mc.starting_value,
            bands=[MonteCarloBand(day=b.day, p5=b.p5, p25=b.p25, p50=b.p50, p75=b.p75, p95=b.p95) for b in mc.bands],
            value_at_risk_95=mc.value_at_risk_95,
        ),
        factor_breakdown=factor_breakdown,
        skipped_tickers=skipped_tickers,
        lookback_years=request.lookback_years,
    )


@router.post(
    "/backtest",
    response_model=BacktestResponse,
    # fetches full price history for every holding + the benchmark
    dependencies=[Depends(rate_limit("10/minute"))],
)
def backtest_portfolio(request: BacktestRequest) -> BacktestResponse:
    if request.period == "custom":
        label, start, end = "Custom period", request.start_date, request.end_date
    else:
        label, start, end = STRESS_PERIODS[request.period]

    tickers = [h.ticker for h in request.holdings]
    weights = {h.ticker: h.weight for h in request.holdings}

    try:
        result = run_backtest(tickers, weights, start=start, end=end)
    except InsufficientDataError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return BacktestResponse(
        period_label=label,
        start_date=start,
        end_date=end,
        dates=result.dates,
        portfolio_path=result.portfolio_path,
        benchmark_path=result.benchmark_path,
        portfolio_total_return=result.portfolio_total_return,
        benchmark_total_return=result.benchmark_total_return,
        portfolio_max_drawdown=result.portfolio_max_drawdown,
        benchmark_max_drawdown=result.benchmark_max_drawdown,
        alpha=result.alpha,
        beta=result.beta,
        skipped_tickers=result.skipped_tickers,
    )


@router.post("/rebalance", response_model=RebalanceResponse, dependencies=[Depends(rate_limit("20/minute"))])
def rebalance(request: RebalanceRequest) -> RebalanceResponse:
    holdings = [(h.ticker, h.weight, h.current_value) for h in request.holdings]
    result = rebalance_portfolio(holdings, request.total_value)

    if len(result.skipped_tickers) == len(request.holdings):
        raise HTTPException(status_code=422, detail="Couldn't fetch a current price for any of the requested tickers")

    return RebalanceResponse(
        orders=[
            RebalanceOrder(
                ticker=o.ticker,
                action=o.action,
                shares=o.shares,
                price=o.price,
                dollar_amount=o.dollar_amount,
                current_value=o.current_value,
                target_value=o.target_value,
            )
            for o in result.orders
        ],
        leftover_cash=result.leftover_cash,
        total_value=result.total_value,
        skipped_tickers=result.skipped_tickers,
    )


@router.post("/export/csv", dependencies=[Depends(rate_limit("20/minute"))])
def export_csv(request: ExportRequest) -> Response:
    csv_bytes = generate_csv(request.analysis, request.ai_insights)
    return Response(
        content=csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="portfoliolens-report.csv"'},
    )


@router.post("/export/pdf", dependencies=[Depends(rate_limit("20/minute"))])
def export_pdf(request: ExportRequest) -> Response:
    pdf_bytes = generate_pdf(request.analysis, request.ai_insights)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": 'attachment; filename="portfoliolens-report.pdf"'},
    )
