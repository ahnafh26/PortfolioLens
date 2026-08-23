"""Rebalancing: target weights + total value -> whole-share buy/sell orders. Rounding gap reported as leftover_cash."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field

import yfinance as yf

from app.services.cache import LATEST_PRICE_CACHE, cached_call

logger = logging.getLogger(__name__)


@cached_call(LATEST_PRICE_CACHE, key_prefix="latest_price")
def fetch_latest_price(ticker: str) -> float | None:
    """Lightweight quote lookup, no fundamentals scrape."""
    try:
        price = yf.Ticker(ticker).fast_info.last_price
    except Exception as exc:
        logger.warning("Failed to fetch latest price for %s: %s", ticker, exc)
        return None
    if price is None or price <= 0:
        return None
    return float(price)


@dataclass
class RebalanceOrderResult:
    ticker: str
    action: str  # "buy" | "sell"
    shares: float
    price: float
    dollar_amount: float
    current_value: float
    target_value: float


@dataclass
class RebalanceResult:
    orders: list[RebalanceOrderResult] = field(default_factory=list)
    leftover_cash: float = 0.0
    total_value: float = 0.0
    skipped_tickers: list[str] = field(default_factory=list)


def compute_rebalance(
    holdings: list[tuple[str, float, float]],  # (ticker, target_weight, current_value)
    total_value: float,
    prices: dict[str, float],
) -> RebalanceResult:
    """Pure function, prices already resolved, so this is testable without touching yfinance."""
    orders: list[RebalanceOrderResult] = []
    leftover_cash = 0.0

    for ticker, weight, current_value in holdings:
        price = prices[ticker]
        target_value = weight * total_value
        delta = target_value - current_value

        exact_shares = delta / price
        # round-half-away-from-zero, not Python's banker's rounding
        whole_shares = math.floor(abs(exact_shares) + 0.5) * (1 if exact_shares >= 0 else -1)

        leftover_cash += delta - whole_shares * price

        if whole_shares == 0:
            continue  # already at target (to the nearest whole share)

        orders.append(
            RebalanceOrderResult(
                ticker=ticker,
                action="buy" if whole_shares > 0 else "sell",
                shares=abs(float(whole_shares)),
                price=price,
                dollar_amount=abs(whole_shares * price),
                current_value=current_value,
                target_value=target_value,
            )
        )

    return RebalanceResult(orders=orders, leftover_cash=leftover_cash, total_value=total_value)


def rebalance_portfolio(
    holdings: list[tuple[str, float, float]],
    total_value: float,
) -> RebalanceResult:
    """Fetches prices, then delegates to compute_rebalance. Unresolvable tickers get skipped, not a failed request."""
    resolved: list[tuple[str, float, float]] = []
    prices: dict[str, float] = {}
    skipped: list[str] = []

    for ticker, weight, current_value in holdings:
        price = fetch_latest_price(ticker)
        if price is None:
            skipped.append(ticker)
            continue
        prices[ticker] = price
        resolved.append((ticker, weight, current_value))

    result = compute_rebalance(resolved, total_value, prices)
    result.skipped_tickers = skipped
    return result
