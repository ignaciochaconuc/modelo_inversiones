from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from investment_system.backtesting import (
    BacktestConfig, OrderSide, PortfolioLedger, SimulatedFill,
)


NOW = datetime(2025, 1, 3, 14, 30, tzinfo=timezone.utc)


def fill(
    side: OrderSide, quantity: float, price: float, *, ticker: str = "AAPL",
    commission: float = 0,
) -> SimulatedFill:
    return SimulatedFill(
        ticker=ticker, side=side, quantity=quantity,
        raw_open_price=price, fill_price=price, notional=quantity * price,
        commission=commission, slippage_cost=0, filled_at=NOW,
    )


def ledger(cash: float = 1_000, *, fractional: bool = True) -> PortfolioLedger:
    return PortfolioLedger(BacktestConfig(initial_cash=cash, allow_fractional_shares=fractional))


def test_initial_cash_and_cash_only_snapshot() -> None:
    book = ledger()
    assert book.initial_cash == book.cash == 1_000
    snapshot = book.mark_to_market({}, NOW)
    assert snapshot.nav == snapshot.cash == 1_000
    assert snapshot.market_value == snapshot.gross_exposure == snapshot.net_exposure == 0
    assert snapshot.weights == {}
    assert snapshot.cash_weight == 1


def test_buy_reduces_cash_and_increases_quantity() -> None:
    book = ledger()
    book.apply_fill(fill(OrderSide.BUY, 10, 10, commission=1))
    assert book.cash == 899
    assert book.positions["AAPL"].quantity == 10
    assert book.positions["AAPL"].average_cost == 10


def test_second_buy_recalculates_volume_weighted_average_cost() -> None:
    book = ledger()
    book.apply_fill(fill(OrderSide.BUY, 10, 10))
    book.apply_fill(fill(OrderSide.BUY, 10, 20))
    assert book.positions["AAPL"].quantity == 20
    assert book.positions["AAPL"].average_cost == 15


def test_partial_sell_preserves_average_cost_and_credits_cash() -> None:
    book = ledger()
    book.apply_fill(fill(OrderSide.BUY, 10, 10))
    book.apply_fill(fill(OrderSide.SELL, 4, 15, commission=1))
    assert book.positions["AAPL"].quantity == 6
    assert book.positions["AAPL"].average_cost == 10
    assert book.cash == 959


def test_total_sell_removes_position() -> None:
    book = ledger()
    book.apply_fill(fill(OrderSide.BUY, 10, 10))
    book.apply_fill(fill(OrderSide.SELL, 10, 12))
    assert "AAPL" not in book.positions
    assert book.cash == 1_020


def test_oversell_fails_without_changing_state() -> None:
    book = ledger()
    book.apply_fill(fill(OrderSide.BUY, 10, 10))
    with pytest.raises(ValueError, match="more shares"):
        book.apply_fill(fill(OrderSide.SELL, 11, 10))
    assert book.positions["AAPL"].quantity == 10
    assert book.cash == 900


def test_buy_without_sufficient_cash_fails_without_changing_state() -> None:
    book = ledger(100)
    with pytest.raises(ValueError, match="insufficient cash"):
        book.apply_fill(fill(OrderSide.BUY, 10, 10, commission=1))
    assert book.cash == 100
    assert book.positions == {}


def test_fractional_shares_follow_configuration() -> None:
    book = ledger(fractional=False)
    with pytest.raises(ValueError, match="fractional shares"):
        book.apply_fill(fill(OrderSide.BUY, 1.5, 10))
    ledger(fractional=True).apply_fill(fill(OrderSide.BUY, 1.5, 10))


def test_mark_to_market_calculates_nav_weights_and_exposure() -> None:
    book = ledger()
    book.apply_fill(fill(OrderSide.BUY, 10, 10))
    book.apply_fill(fill(OrderSide.BUY, 5, 20, ticker="MSFT"))
    snapshot = book.mark_to_market({"AAPL": 12, "MSFT": 18}, NOW)
    assert snapshot.cash == 800
    assert snapshot.market_value == 210
    assert snapshot.nav == 1_010
    assert snapshot.weights["AAPL"] == pytest.approx(120 / 1_010)
    assert snapshot.weights["MSFT"] == pytest.approx(90 / 1_010)
    assert snapshot.cash_weight == pytest.approx(800 / 1_010)
    assert sum(snapshot.weights.values()) + snapshot.cash_weight == pytest.approx(1)
    assert snapshot.gross_exposure == snapshot.net_exposure == pytest.approx(210 / 1_010)


def test_mark_to_market_requires_every_held_price_and_is_atomic() -> None:
    book = ledger()
    book.apply_fill(fill(OrderSide.BUY, 10, 10))
    with pytest.raises(ValueError, match="missing market prices"):
        book.mark_to_market({}, NOW)
    assert book.positions["AAPL"].market_price == 10
    with pytest.raises(ValueError, match="invalid market price"):
        book.mark_to_market({"AAPL": -1}, NOW)
    assert book.positions["AAPL"].market_price == 10


def test_forward_split_preserves_economic_value() -> None:
    book = ledger()
    book.apply_fill(fill(OrderSide.BUY, 10, 100))
    before = book.positions["AAPL"].market_value
    book.apply_split("AAPL", 2)
    position = book.positions["AAPL"]
    assert position.quantity == 20
    assert position.average_cost == 50
    assert position.market_price == 50
    assert position.market_value == before


def test_reverse_split_preserves_economic_value() -> None:
    book = ledger()
    book.apply_fill(fill(OrderSide.BUY, 10, 50))
    before = book.positions["AAPL"].market_value
    book.apply_split("AAPL", 0.5)
    position = book.positions["AAPL"]
    assert position.quantity == 5
    assert position.average_cost == 100
    assert position.market_price == 100
    assert position.market_value == before


def test_split_rejects_invalid_factor_and_fractional_result() -> None:
    book = ledger(fractional=False)
    book.apply_fill(fill(OrderSide.BUY, 3, 10))
    with pytest.raises(ValueError, match="split_factor"):
        book.apply_split("AAPL", 0)
    with pytest.raises(ValueError, match="fractional shares"):
        book.apply_split("AAPL", 0.5)
    assert book.positions["AAPL"].quantity == 3


def test_dividend_credits_quantity_times_cash_amount() -> None:
    book = ledger()
    book.apply_fill(fill(OrderSide.BUY, 10, 10))
    assert book.apply_dividend("AAPL", 0.25) == 2.5
    assert book.cash == 902.5


def test_dividend_for_unowned_ticker_is_noop() -> None:
    book = ledger()
    assert book.apply_dividend("MSFT", 1) == 0
    assert book.cash == 1_000


def test_position_quantities_cannot_be_negative() -> None:
    with pytest.raises(ValidationError):
        SimulatedFill(
            ticker="AAPL", side="BUY", quantity=-1, raw_open_price=10,
            fill_price=10, notional=10, commission=0, slippage_cost=0, filled_at=NOW,
        )

