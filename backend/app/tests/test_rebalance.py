from __future__ import annotations

import pytest

from app.services import rebalance


def test_compute_rebalance_buy_only_from_cash_hand_computed():
    # $10,000 total, 60/40 target, starting from $0 held in either.
    # AAPL: target $6,000 @ $150/share = 40 shares exactly.
    # MSFT: target $4,000 @ $400/share = 10 shares exactly.
    holdings = [("AAPL", 0.6, 0.0), ("MSFT", 0.4, 0.0)]
    prices = {"AAPL": 150.0, "MSFT": 400.0}

    result = rebalance.compute_rebalance(holdings, total_value=10_000.0, prices=prices)

    by_ticker = {o.ticker: o for o in result.orders}
    assert by_ticker["AAPL"].action == "buy"
    assert by_ticker["AAPL"].shares == pytest.approx(40)
    assert by_ticker["AAPL"].dollar_amount == pytest.approx(6000.0)
    assert by_ticker["MSFT"].action == "buy"
    assert by_ticker["MSFT"].shares == pytest.approx(10)
    assert result.leftover_cash == pytest.approx(0.0)


def test_compute_rebalance_produces_sell_orders_when_overweight():
    # Already holding $8,000 of AAPL against a $5,000 target -> must sell.
    holdings = [("AAPL", 0.5, 8_000.0)]
    prices = {"AAPL": 100.0}

    result = rebalance.compute_rebalance(holdings, total_value=10_000.0, prices=prices)

    assert len(result.orders) == 1
    order = result.orders[0]
    assert order.action == "sell"
    assert order.shares == pytest.approx(30)  # (8000-5000)/100
    assert order.dollar_amount == pytest.approx(3000.0)


def test_compute_rebalance_skips_holdings_already_at_target():
    # Exactly at target already -> no trade needed for this ticker.
    holdings = [("AAPL", 0.5, 5_000.0), ("MSFT", 0.5, 4_000.0)]
    prices = {"AAPL": 100.0, "MSFT": 200.0}

    result = rebalance.compute_rebalance(holdings, total_value=10_000.0, prices=prices)

    tickers_traded = {o.ticker for o in result.orders}
    assert "AAPL" not in tickers_traded  # already exactly at $5,000 target
    assert "MSFT" in tickers_traded  # $4,000 held vs $5,000 target -> buy 5 shares


def test_compute_rebalance_rounds_to_whole_shares_and_reports_leftover_cash():
    # Target $1,000 @ $300/share = 3.333... shares -> rounds to 3 whole
    # shares ($900), leaving $100 of the perfect-fractional target
    # unallocated as leftover cash.
    holdings = [("AAPL", 1.0, 0.0)]
    prices = {"AAPL": 300.0}

    result = rebalance.compute_rebalance(holdings, total_value=1_000.0, prices=prices)

    assert result.orders[0].shares == pytest.approx(3)
    assert result.orders[0].dollar_amount == pytest.approx(900.0)
    assert result.leftover_cash == pytest.approx(100.0)


def test_compute_rebalance_rounds_half_up_not_bankers_rounding():
    # delta/price = exactly 2.5 shares -> should round to 3 (away from
    # zero), not 2 (which plain Python round() would give via banker's
    # rounding on a tie).
    holdings = [("AAPL", 1.0, 0.0)]
    prices = {"AAPL": 100.0}

    result = rebalance.compute_rebalance(holdings, total_value=250.0, prices=prices)

    assert result.orders[0].shares == pytest.approx(3)


def test_rebalance_portfolio_reports_skipped_tickers_for_unresolvable_prices(monkeypatch):
    def fake_fetch_latest_price(ticker: str) -> float | None:
        return None if ticker == "DEAD" else 100.0

    monkeypatch.setattr(rebalance, "fetch_latest_price", fake_fetch_latest_price)

    result = rebalance.rebalance_portfolio(
        holdings=[("AAPL", 0.5, 0.0), ("DEAD", 0.5, 0.0)],
        total_value=10_000.0,
    )

    assert result.skipped_tickers == ["DEAD"]
    assert {o.ticker for o in result.orders} == {"AAPL"}
