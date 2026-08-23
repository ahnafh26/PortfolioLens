"""AI Portfolio Assistant. LLM only narrates numbers we already computed, never invents or allocates.
Falls back to templated text when no OPENROUTER_API_KEY is set.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import yfinance as yf

from app.services.classification import concentration_flags, fetch_company_profile
from app.services.llm_client import complete_chat, is_configured

logger = logging.getLogger(__name__)

# rules-of-thumb thresholds, not derived from the data
SINGLE_HOLDING_CONCENTRATION_THRESHOLD = 0.20
SECTOR_CONCENTRATION_THRESHOLD = 0.50
HIGH_CORRELATION_THRESHOLD = 0.85
HIGH_VOLATILITY_THRESHOLD = 0.30  # annualized

DISCLAIMER = (
    "This is general portfolio analytics, not personalized financial advice -- "
    "consider talking to a licensed advisor before acting on it."
)


# Rule-based signals (source of truth)

@dataclass(frozen=True)
class Signal:
    severity: str  # "warning" | "info"
    message: str


def compute_signals(
    weights: dict[str, float],
    portfolio_volatility: float,
    sector_breakdown: dict[str, float],
    correlation_tickers: list[str],
    correlation_matrix: list[list[float]],
) -> list[Signal]:
    signals: list[Signal] = []

    # single-holding concentration
    for ticker, weight in sorted(weights.items(), key=lambda kv: kv[1], reverse=True):
        if weight >= SINGLE_HOLDING_CONCENTRATION_THRESHOLD:
            signals.append(
                Signal(
                    "warning",
                    f"{ticker} makes up {weight:.0%} of the portfolio -- a single-name move in "
                    f"either direction will dominate overall performance.",
                )
            )

    # sector concentration
    for label, weight in concentration_flags(sector_breakdown, threshold=SECTOR_CONCENTRATION_THRESHOLD):
        signals.append(
            Signal(
                "warning",
                f"{weight:.0%} of the portfolio is in {label}. Consider adding holdings from "
                f"less-correlated sectors to reduce concentration risk.",
            )
        )

    # high correlation between meaningfully-weighted holdings
    for i, t1 in enumerate(correlation_tickers):
        for j, t2 in enumerate(correlation_tickers):
            if j <= i:
                continue
            corr = correlation_matrix[i][j]
            if corr >= HIGH_CORRELATION_THRESHOLD and weights.get(t1, 0) > 0.05 and weights.get(t2, 0) > 0.05:
                signals.append(
                    Signal(
                        "info",
                        f"{t1} and {t2} are highly correlated ({corr:.2f}) -- holding both adds "
                        f"less diversification benefit than the weight split suggests.",
                    )
                )

    # overall volatility
    if portfolio_volatility >= HIGH_VOLATILITY_THRESHOLD:
        signals.append(
            Signal(
                "warning",
                f"Annualized volatility is {portfolio_volatility:.0%}, well above a broad-market "
                f"index fund (S&P 500 has historically run ~15-20%). Expect a bumpier ride.",
            )
        )

    if not signals:
        signals.append(Signal("info", "No major concentration or correlation red flags at these weights."))

    return signals


# Narration (LLM, falls back to rule-based)

@dataclass
class InsightsResult:
    insights: list[str]
    source: str  # "llm" | "rule_based"


def _fallback_insights(signals: list[Signal]) -> list[str]:
    return [s.message for s in signals] + [DISCLAIMER]


def generate_insights(
    weights: dict[str, float],
    portfolio_return: float,
    portfolio_volatility: float,
    sharpe_ratio: float,
    sector_breakdown: dict[str, float],
    correlation_tickers: list[str],
    correlation_matrix: list[list[float]],
) -> InsightsResult:
    signals = compute_signals(weights, portfolio_volatility, sector_breakdown, correlation_tickers, correlation_matrix)

    if not is_configured():
        return InsightsResult(insights=_fallback_insights(signals), source="rule_based")

    weights_line = ", ".join(f"{t} {w:.0%}" for t, w in sorted(weights.items(), key=lambda kv: -kv[1]))
    sectors_line = ", ".join(f"{k} {v:.0%}" for k, v in sorted(sector_breakdown.items(), key=lambda kv: -kv[1]))
    signals_line = "\n".join(f"- {s.message}" for s in signals)

    prompt = (
        "You are a portfolio risk analyst writing brief notes for a retail investor's dashboard.\n"
        "Use ONLY the computed data below -- do not invent any numbers, holdings, or events not listed.\n\n"
        f"Holdings (weight): {weights_line}\n"
        f"Sector exposure: {sectors_line}\n"
        f"Annualized return: {portfolio_return:.1%}, volatility: {portfolio_volatility:.1%}, Sharpe ratio: {sharpe_ratio:.2f}\n"
        f"Automatically detected risk signals:\n{signals_line}\n\n"
        "Write 2-4 short bullet points (each 1-2 sentences) explaining what stands out about this "
        "portfolio's risk profile in plain English, grounded in the signals above. Do not give specific "
        "buy/sell/dollar-amount instructions or claim to be a licensed advisor. Return only the bullet "
        "points, one per line, no preamble."
    )

    reply = complete_chat([{"role": "user", "content": prompt}])
    if reply is None:
        return InsightsResult(insights=_fallback_insights(signals), source="rule_based")

    lines = [line.strip("-• \t") for line in reply.splitlines() if line.strip()]
    lines.append(DISCLAIMER)
    return InsightsResult(insights=lines, source="llm")


# Per-ticker research

@dataclass
class TickerResearchResult:
    ticker: str
    name: str
    sector: str
    market_cap_bucket: str
    trailing_pe: float | None
    summary: str
    source: str


def generate_ticker_research(ticker: str) -> TickerResearchResult:
    profile = fetch_company_profile(ticker)

    try:
        info = yf.Ticker(ticker).get_info()
    except Exception as exc:
        logger.warning("Failed to fetch fundamentals for %s: %s", ticker, exc)
        info = {}

    trailing_pe = info.get("trailingPE")
    business_summary = info.get("longBusinessSummary", "")

    fallback_summary = (
        f"{profile.name} ({ticker}) is classified under {profile.sector}"
        f"{' (' + profile.market_cap_bucket + ')' if not profile.is_fund else ''}."
        + (f" Trailing P/E: {trailing_pe:.1f}." if trailing_pe else "")
    )

    if not is_configured():
        return TickerResearchResult(
            ticker=ticker, name=profile.name, sector=profile.sector, market_cap_bucket=profile.market_cap_bucket,
            trailing_pe=trailing_pe, summary=fallback_summary, source="rule_based",
        )

    prompt = (
        "Summarize the following company/fund in 2-3 sentences for a retail investor comparing it "
        "against other holdings in their portfolio. Use ONLY the facts given -- do not invent recent "
        "news, earnings figures, or price targets not present below.\n\n"
        f"Name: {profile.name} ({ticker})\n"
        f"Classification: {profile.sector}\n"
        f"Trailing P/E: {trailing_pe if trailing_pe else 'unavailable'}\n"
        f"Business description: {business_summary[:800] if business_summary else 'unavailable'}\n\n"
        "Return only the summary, no preamble."
    )
    reply = complete_chat([{"role": "user", "content": prompt}], max_tokens=250)
    if reply is None:
        return TickerResearchResult(
            ticker=ticker, name=profile.name, sector=profile.sector, market_cap_bucket=profile.market_cap_bucket,
            trailing_pe=trailing_pe, summary=fallback_summary, source="rule_based",
        )

    return TickerResearchResult(
        ticker=ticker, name=profile.name, sector=profile.sector, market_cap_bucket=profile.market_cap_bucket,
        trailing_pe=trailing_pe, summary=reply.strip(), source="llm",
    )


# Suggested allocations (deterministic, no LLM)

RISK_PROFILE_RATIONALE = {
    "conservative": "Weighted inversely to each holding's volatility, so steadier holdings get more capital.",
    "balanced": "Split evenly across holdings -- a neutral starting point that doesn't tilt toward any one signal.",
    "growth": "Tilted toward holdings with the best risk-adjusted return (Sharpe ratio) at these weights.",
    "aggressive": "Tilted toward holdings with the highest raw expected return, accepting more volatility for it.",
}


def suggested_allocation(
    holdings: list[tuple[str, float, float]],  # (ticker, annual_return, annual_volatility)
    risk_profile: str,
) -> tuple[dict[str, float], str]:
    """(weights, rationale). Simple explainable heuristics, not the frontier optimizer."""
    tickers = [t for t, _, _ in holdings]
    returns = {t: r for t, r, _ in holdings}
    vols = {t: v for t, _, v in holdings}

    if risk_profile == "conservative":
        # inverse-volatility weighting
        scores = {t: 1.0 / max(vols[t], 1e-6) for t in tickers}
    elif risk_profile == "growth":
        sharpe = {t: (returns[t] - 0.04) / max(vols[t], 1e-6) for t in tickers}
        # shift positive, keep ordering
        floor = min(sharpe.values())
        scores = {t: (sharpe[t] - floor) + 0.05 for t in tickers}
    elif risk_profile == "aggressive":
        floor = min(returns.values())
        scores = {t: (returns[t] - floor) + 0.05 for t in tickers}
    else:  # balanced / unrecognized: equal weight
        scores = {t: 1.0 for t in tickers}

    total = sum(scores.values())
    weights = {t: s / total for t, s in scores.items()}
    return weights, RISK_PROFILE_RATIONALE.get(risk_profile, RISK_PROFILE_RATIONALE["balanced"])
