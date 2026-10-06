from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from investment_system.backtesting import (
    BacktestConfig, BacktestPosition, BacktestResult, OrderSide,
    SimulatedFill, SimulatedOrder, TargetAllocation,
)


NOW = datetime(2025, 1, 2, 21, 15, tzinfo=timezone.utc)


def test_backtest_config_rejects_negative_cash_or_costs() -> None:
    with pytest.raises(ValidationError):
        BacktestConfig(initial_cash=-1)
    with pytest.raises(ValidationError):
        BacktestConfig(initial_cash=1, commission_bps=-1)
    with pytest.raises(ValidationError):
        BacktestConfig(initial_cash=1, slippage_bps=-1)
    with pytest.raises(ValidationError):
        BacktestConfig(initial_cash=1, commission_bps=float("inf"))


def test_target_allocation_requires_long_only_weights_plus_cash_equal_one() -> None:
    valid = TargetAllocation(generated_at=NOW, weights={"aapl": 0.6}, cash_weight=0.4)
    assert valid.weights == {"AAPL": 0.6}
    with pytest.raises(ValidationError, match="must equal 1"):
        TargetAllocation(generated_at=NOW, weights={"AAPL": 0.5}, cash_weight=0.4)
    with pytest.raises(ValidationError):
        TargetAllocation(generated_at=NOW, weights={"AAPL": -0.1}, cash_weight=1)


def test_orders_and_fills_reject_invalid_quantities() -> None:
    with pytest.raises(ValidationError):
        SimulatedOrder(
            order_id="order-1", allocation_id="allocation-1",
            ticker="AAPL", side=OrderSide.BUY, quantity=0, submitted_at=NOW,
            execution_date=NOW.date(), target_weight=0.1, reference_price=100,
        )
    with pytest.raises(ValidationError):
        SimulatedFill(
            fill_id="fill-1", order_id="order-1", allocation_id="allocation-1",
            ticker="AAPL", side=OrderSide.BUY, quantity=0, raw_open_price=100,
            fill_price=100, notional=100, commission=0, slippage_cost=0, filled_at=NOW,
        )


def test_fill_validates_notional_and_slippage_audit_values() -> None:
    fill = SimulatedFill(
        fill_id="fill-1", order_id="order-1", allocation_id="allocation-1",
        ticker="AAPL", side=OrderSide.BUY, quantity=10, raw_open_price=100,
        fill_price=100.1, notional=1_001, commission=1, slippage_cost=1, filled_at=NOW,
    )
    assert fill.notional == 1_001
    with pytest.raises(ValidationError, match="notional"):
        fill.model_copy(update={"notional": 999}).model_validate(
            {**fill.model_dump(), "notional": 999}
        )
    with pytest.raises(ValidationError, match="slippage_cost"):
        SimulatedFill(**{**fill.model_dump(), "slippage_cost": 2})


def test_backtest_timestamps_must_be_timezone_aware() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        TargetAllocation(generated_at=datetime(2025, 1, 1), weights={}, cash_weight=1)


def test_position_market_value_is_calculated_not_persisted_input() -> None:
    position = BacktestPosition(ticker="AAPL", quantity=2, average_cost=10, market_price=12)
    assert position.market_value == 24
    with pytest.raises(ValidationError):
        BacktestPosition(ticker="AAPL", quantity=2, average_cost=10, market_price=12, market_value=999)


def test_backtest_result_is_an_empty_engine_envelope() -> None:
    result = BacktestResult(run_id="run-1", config=BacktestConfig(initial_cash=10_000))
    assert result.snapshots == result.orders == result.fills == []
    assert result.metadata == {}
