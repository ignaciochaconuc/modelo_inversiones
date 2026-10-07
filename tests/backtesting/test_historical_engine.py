from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from investment_system.backtesting import (
    BacktestConfig, BacktestPosition, PortfolioLedger,
    BacktestDataError,
    CashFlowType,
    HistoricalBacktestEngine,
    OrderSide,
    OrderStatus,
    TargetAllocation,
    UnmodelledCorporateActionError,
)
from investment_system.data.calendar import XNYSTradingCalendar


NY = ZoneInfo("America/New_York")


class MemoryMarketStore:
    def __init__(
        self,
        bars: dict[str, pd.DataFrame],
        actions: dict[str, pd.DataFrame] | None = None,
        events: pd.DataFrame | None = None,
    ) -> None:
        self.bars = bars
        self.actions = actions or {}
        self.events = events if events is not None else pd.DataFrame()

    def read_bars(self, ticker: str) -> pd.DataFrame:
        return self.bars.get(ticker, pd.DataFrame()).copy()

    def read_actions(self, ticker: str) -> pd.DataFrame:
        return self.actions.get(ticker, pd.DataFrame()).copy()

    def read_corporate_action_events(self) -> pd.DataFrame:
        return self.events.copy()


def bar(day: date, open_: float, close: float, *, available_hour: int = 20) -> dict:
    return {
        "ticker": "unused",
        "trading_date": day,
        "open": open_,
        "close": close,
        "available_at": datetime(day.year, day.month, day.day, available_hour, tzinfo=NY),
    }


def frame(ticker: str, *rows: dict) -> pd.DataFrame:
    result = pd.DataFrame(rows)
    if not result.empty:
        result["ticker"] = ticker
    return result


def action(ticker: str, day: date, kind: str, *, split: float | None = None,
           dividend: float | None = None) -> dict:
    return {
        "ticker": ticker,
        "effective_date": day,
        "action_type": kind,
        "split_factor": split,
        "dividend_cash": dividend,
    }


def engine(
    store: MemoryMarketStore,
    *, cash: float = 1_000,
    commission_bps: float = 0,
    slippage_bps: float = 0,
    fractional: bool = True,
) -> HistoricalBacktestEngine:
    return HistoricalBacktestEngine(
        BacktestConfig(
            initial_cash=cash,
            commission_bps=commission_bps,
            slippage_bps=slippage_bps,
            allow_fractional_shares=fractional,
        ),
        store,
        XNYSTradingCalendar(),
    )


def allocation(subject: HistoricalBacktestEngine, day: date, **weights: float) -> TargetAllocation:
    return TargetAllocation(
        generated_at=subject.decision_time(day),
        weights=weights,
        cash_weight=1 - sum(weights.values()),
        risk_decision_id="risk-approved-test",
    )


def test_decision_uses_raw_close_and_fills_only_at_next_raw_open_with_costs() -> None:
    thursday, friday = date(2025, 1, 2), date(2025, 1, 3)
    store = MemoryMarketStore({
        "AAPL": frame("AAPL", bar(thursday, 9, 10), bar(friday, 11, 12)),
    })
    subject = engine(store, commission_bps=10, slippage_bps=100)

    result = subject.run(thursday, friday, {thursday: allocation(subject, thursday, AAPL=0.5)})

    order, fill, execution = result.orders[0], result.fills[0], result.executions[0]
    assert order.reference_price == 10
    assert order.quantity == 50
    assert order.execution_date == friday
    assert order.submitted_at == subject.decision_time(thursday)
    assert fill.filled_at == subject.calendar.session_open(friday)
    assert fill.raw_open_price == 11
    assert fill.fill_price == pytest.approx(11.11)
    assert fill.slippage_cost == pytest.approx(5.5)
    assert fill.commission == pytest.approx(fill.notional * 0.001)
    assert execution.status == OrderStatus.FILLED
    assert fill.order_id == order.order_id
    assert fill.allocation_id == order.allocation_id == result.allocations[0].allocation_id
    assert result.snapshots[0].positions == []
    assert result.snapshots[1].positions[0].market_price == 12


def test_next_session_skips_weekend_and_exchange_holiday() -> None:
    friday, tuesday = date(2025, 1, 17), date(2025, 1, 21)
    store = MemoryMarketStore({
        "AAPL": frame("AAPL", bar(friday, 10, 10), bar(tuesday, 12, 12)),
    })
    subject = engine(store)
    result = subject.run(friday, tuesday, {friday: allocation(subject, friday, AAPL=0.5)})
    assert result.orders[0].execution_date == tuesday
    assert result.fills[0].filled_at == subject.calendar.session_open(tuesday)


def test_friday_decision_fills_on_monday_when_monday_is_a_session() -> None:
    friday, monday = date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore({
        "AAPL": frame("AAPL", bar(friday, 10, 10), bar(monday, 11, 11)),
    })
    subject = engine(store)
    result = subject.run(friday, monday, {friday: allocation(subject, friday, AAPL=0.5)})
    assert result.orders[0].execution_date == monday
    assert result.fills[0].filled_at.date() == monday


def test_missing_execution_open_is_unfilled_once_and_never_rolls_forward() -> None:
    friday, monday, tuesday = date(2025, 1, 3), date(2025, 1, 6), date(2025, 1, 7)
    store = MemoryMarketStore({
        "AAPL": frame("AAPL", bar(friday, 10, 10), bar(tuesday, 20, 20)),
    })
    subject = engine(store)
    result = subject.run(friday, tuesday, {friday: allocation(subject, friday, AAPL=1)})
    assert result.fills == []
    assert len(result.executions) == 1
    assert result.executions[0].execution_date == monday
    assert result.executions[0].status == OrderStatus.UNFILLED
    assert result.executions[0].reason == "missing_execution_open"


def test_late_close_cannot_be_used_for_the_same_decision() -> None:
    day = date(2025, 1, 2)
    store = MemoryMarketStore({"AAPL": frame("AAPL", bar(day, 10, 10, available_hour=21))})
    subject = engine(store)
    with pytest.raises(BacktestDataError, match="unavailable by decision_time"):
        subject.run(day, day, {day: allocation(subject, day, AAPL=0.5)})


def test_late_held_close_is_stale_and_cannot_change_decision_nav() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore({
        "AAPL": frame(
            "AAPL", bar(d1, 10, 10), bar(d2, 10, 10),
            bar(d3, 10, 1_000, available_hour=21),
        ),
    })
    subject = engine(store)
    result = subject.run(d1, d3, {d1: allocation(subject, d1, AAPL=1)})
    assert result.snapshots[-1].nav == 1_000
    assert result.snapshots[-1].positions[0].market_price == 10
    assert result.snapshots[-1].stale_price_tickers == ["AAPL"]


def test_sell_executes_before_buy_and_proceeds_fund_the_buy() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore({
        "AAPL": frame("AAPL", bar(d1, 10, 10), bar(d2, 10, 10), bar(d3, 10, 10)),
        "MSFT": frame("MSFT", bar(d1, 10, 10), bar(d2, 10, 10), bar(d3, 10, 10)),
    })
    subject = engine(store)
    allocations = {
        d1: allocation(subject, d1, AAPL=1),
        d2: allocation(subject, d2, MSFT=1),
    }
    result = subject.run(d1, d3, allocations)
    day_three_fills = [item for item in result.fills if item.filled_at.date() == d3]
    assert [item.side for item in day_three_fills] == [OrderSide.SELL, OrderSide.BUY]
    assert result.snapshots[-1].positions[0].ticker == "MSFT"
    assert result.snapshots[-1].cash == pytest.approx(0)


def test_target_zero_liquidates_with_adverse_sell_slippage_and_commission() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore({
        "AAPL": frame("AAPL", bar(d1, 10, 10), bar(d2, 10, 10), bar(d3, 20, 20)),
    })
    subject = engine(store, slippage_bps=100, commission_bps=10)
    result = subject.run(d1, d3, {
        d1: allocation(subject, d1, AAPL=0.5),
        d2: allocation(subject, d2),
    })
    sell = [item for item in result.fills if item.side == OrderSide.SELL][0]
    assert sell.raw_open_price == 20
    assert sell.fill_price == pytest.approx(19.8)
    assert sell.slippage_cost == pytest.approx((20 - 19.8) * sell.quantity)
    assert sell.commission == pytest.approx(sell.notional * 0.001)
    assert result.snapshots[-1].positions == []


def test_unchanged_target_creates_no_rebalance_order() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    store = MemoryMarketStore({"AAPL": frame("AAPL", bar(d1, 10, 10), bar(d2, 10, 10))})
    subject = engine(store)
    result = subject.run(d1, d2, {
        d1: allocation(subject, d1, AAPL=0.5),
        d2: allocation(subject, d2, AAPL=0.5),
    })
    assert len(result.orders) == 1


def test_overnight_gap_reduces_buy_to_cash_without_negative_balance() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    store = MemoryMarketStore({"AAPL": frame("AAPL", bar(d1, 10, 10), bar(d2, 20, 20))})
    subject = engine(store)
    result = subject.run(d1, d2, {d1: allocation(subject, d1, AAPL=1)})
    assert result.orders[0].quantity == 100
    assert result.fills[0].quantity == 50
    assert result.executions[0].status == OrderStatus.PARTIALLY_FILLED
    assert result.executions[0].quantity_reduced
    assert result.snapshots[-1].cash == 0


def test_whole_share_policy_floors_sizing_and_leaves_residual_cash() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    store = MemoryMarketStore({"AAPL": frame("AAPL", bar(d1, 100, 100), bar(d2, 100, 100))})
    subject = engine(store, fractional=False)
    result = subject.run(d1, d2, {d1: allocation(subject, d1, AAPL=0.555)})
    assert result.orders[0].quantity == 5
    assert result.fills[0].quantity == 5
    assert result.snapshots[-1].cash == 500


def test_fractional_policy_accepts_non_integer_quantity() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    store = MemoryMarketStore({"AAPL": frame("AAPL", bar(d1, 30, 30), bar(d2, 30, 30))})
    subject = engine(store, cash=100)
    result = subject.run(d1, d2, {d1: allocation(subject, d1, AAPL=1)})
    assert result.fills[0].quantity == pytest.approx(100 / 30)
    assert not result.fills[0].quantity.is_integer()


def test_missing_close_uses_flagged_stale_price_for_valuation_only() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore({"AAPL": frame("AAPL", bar(d1, 10, 10), bar(d2, 10, 12))})
    subject = engine(store)
    result = subject.run(d1, d3, {d1: allocation(subject, d1, AAPL=0.5)})
    assert result.snapshots[-1].positions[0].market_price == 12
    assert result.snapshots[-1].stale_price_tickers == ["AAPL"]


def test_held_position_without_any_valid_prior_price_fails_valuation() -> None:
    day = date(2025, 1, 2)
    subject = engine(MemoryMarketStore({}))
    ledger = PortfolioLedger(BacktestConfig(initial_cash=100))
    ledger._positions["AAPL"] = BacktestPosition.model_construct(
        ticker="AAPL", quantity=1, average_cost=10, market_price=0,
    )
    with pytest.raises(BacktestDataError, match="no prior valid valuation price"):
        subject._valuation_prices(day, ledger, {})


def test_adjusted_prices_are_never_used_for_orders_fills_or_valuation() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    rows = frame("AAPL", bar(d1, 10, 10), bar(d2, 11, 12))
    rows["adjusted_open"] = [1, 1.1]
    rows["adjusted_close"] = [1, 1.2]
    subject = engine(MemoryMarketStore({"AAPL": rows}))
    result = subject.run(d1, d2, {d1: allocation(subject, d1, AAPL=0.5)})
    assert result.orders[0].reference_price == 10
    assert result.fills[0].raw_open_price == 11
    assert result.snapshots[-1].positions[0].market_price == 12


def test_forward_split_adjusts_held_units_and_average_cost_pre_open() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": frame("AAPL", bar(d1, 100, 100), bar(d2, 100, 100), bar(d3, 50, 50))},
        {"AAPL": pd.DataFrame([action("AAPL", d3, "split", split=2)])},
    )
    subject = engine(store)
    result = subject.run(d1, d3, {d1: allocation(subject, d1, AAPL=1)})
    position = result.snapshots[-1].positions[0]
    assert position.quantity == 20
    assert position.average_cost == 50
    assert result.snapshots[-1].nav == 1_000


def test_reverse_split_with_fractional_shares_preserves_exact_units() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": frame("AAPL", bar(d1, 100, 100), bar(d2, 100, 100), bar(d3, 200, 200))},
        {"AAPL": pd.DataFrame([action("AAPL", d3, "split", split=0.5)])},
    )
    subject = engine(store, cash=300)
    result = subject.run(d1, d3, {d1: allocation(subject, d1, AAPL=1)})
    position = result.snapshots[-1].positions[0]
    assert position.quantity == 1.5
    assert position.average_cost == 200
    assert result.cash_flows == []


def test_reverse_split_whole_shares_creates_cash_in_lieu_and_realized_pnl() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": frame("AAPL", bar(d1, 100, 100), bar(d2, 100, 100), bar(d3, 210, 200))},
        {"AAPL": pd.DataFrame([action("AAPL", d3, "split", split=0.5)])},
    )
    subject = engine(store, cash=300, fractional=False)
    result = subject.run(d1, d3, {d1: allocation(subject, d1, AAPL=1)})
    position = result.snapshots[-1].positions[0]
    assert position.quantity == 1
    assert result.snapshots[-1].cash == 105
    assert result.realized_pnl == 5
    flow = result.cash_flows[0]
    assert flow.cash_flow_type == CashFlowType.CASH_IN_LIEU
    assert flow.quantity == pytest.approx(0.5)
    assert flow.amount == 105


def test_reverse_split_also_adjusts_pending_order_before_open() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": frame("AAPL", bar(d1, 100, 100), bar(d2, 100, 100), bar(d3, 200, 200))},
        {"AAPL": pd.DataFrame([action("AAPL", d3, "split", split=0.5)])},
    )
    subject = engine(store, cash=300, fractional=False)
    result = subject.run(d1, d3, {
        d1: allocation(subject, d1, AAPL=1),
        d2: allocation(subject, d2),
    })
    sell = [item for item in result.fills if item.side == OrderSide.SELL][0]
    sell_execution = [item for item in result.executions if item.order_id == sell.order_id][0]
    assert sell.quantity == 1
    assert sell_execution.requested_quantity == 1.5
    assert sell_execution.status == OrderStatus.PARTIALLY_FILLED
    assert result.snapshots[-1].positions == []
    assert result.snapshots[-1].nav == 300


def test_fractional_split_settlement_requires_that_sessions_raw_open() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": frame("AAPL", bar(d1, 100, 100), bar(d2, 100, 100))},
        {"AAPL": pd.DataFrame([action("AAPL", d3, "split", split=0.5)])},
    )
    subject = engine(store, cash=300, fractional=False)
    with pytest.raises(BacktestDataError, match="cash-in-lieu"):
        subject.run(d1, d3, {d1: allocation(subject, d1, AAPL=1)})


def test_dividend_is_credited_after_open_fill_and_before_final_snapshot() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {
            "AAPL": frame("AAPL", bar(d1, 10, 10), bar(d2, 10, 10), bar(d3, 10, 10)),
            "MSFT": frame("MSFT", bar(d2, 10, 10), bar(d3, 11, 11)),
        },
        {"AAPL": pd.DataFrame([action("AAPL", d3, "dividend", dividend=0.25)])},
    )
    subject = engine(store)
    result = subject.run(d1, d3, {
        d1: allocation(subject, d1, AAPL=0.5),
        d2: allocation(subject, d2, AAPL=0.5, MSFT=0.5),
    })
    msft_fill = [item for item in result.fills if item.ticker == "MSFT"][0]
    assert msft_fill.filled_at < result.cash_flows[0].occurred_at
    assert result.orders[-1].quantity == 50
    assert msft_fill.quantity == pytest.approx(500 / 11)
    assert result.executions[-1].status == OrderStatus.PARTIALLY_FILLED
    assert result.cash_flows[0].amount == 12.5
    assert result.snapshots[-1].cash == 12.5
    assert result.snapshots[-1].nav == 1_012.5


def test_sell_on_ex_date_keeps_pre_open_dividend_entitlement() -> None:
    d1, d2, ex_date = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": frame(
            "AAPL", bar(d1, 10, 10), bar(d2, 10, 10), bar(ex_date, 10, 10),
        )},
        {"AAPL": pd.DataFrame([action("AAPL", ex_date, "dividend", dividend=1)])},
    )
    subject = engine(store, cash=100)
    allocations = {
        d1: allocation(subject, d1, AAPL=1),
        d2: allocation(subject, d2),
    }

    first = subject.run(d1, ex_date, allocations)
    second = subject.run(d1, ex_date, allocations)

    assert first.snapshots[-1].positions == []
    assert len(first.cash_flows) == 1
    assert first.cash_flows[0].quantity == 10
    assert first.cash_flows[0].amount == 10
    assert first.snapshots[-1].cash == 110
    assert first.cash_flows == second.cash_flows
    assert first.snapshots[-1].nav == second.snapshots[-1].nav


def test_buy_on_ex_date_does_not_create_dividend_entitlement() -> None:
    decision_date, ex_date = date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": frame(
            "AAPL", bar(decision_date, 10, 10), bar(ex_date, 10, 10),
        )},
        {"AAPL": pd.DataFrame([action("AAPL", ex_date, "dividend", dividend=1)])},
    )
    subject = engine(store, cash=100)
    result = subject.run(
        decision_date, ex_date,
        {decision_date: allocation(subject, decision_date, AAPL=1)},
    )

    assert result.snapshots[-1].positions[0].quantity == 10
    assert result.cash_flows == []
    assert result.snapshots[-1].cash == 0


def test_partial_sell_on_ex_date_uses_full_pre_open_quantity() -> None:
    d1, d2, ex_date = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": frame(
            "AAPL", bar(d1, 10, 10), bar(d2, 10, 10), bar(ex_date, 10, 10),
        )},
        {"AAPL": pd.DataFrame([action("AAPL", ex_date, "dividend", dividend=1)])},
    )
    subject = engine(store, cash=100)
    result = subject.run(d1, ex_date, {
        d1: allocation(subject, d1, AAPL=1),
        d2: allocation(subject, d2, AAPL=0.6),
    })

    assert result.snapshots[-1].positions[0].quantity == 6
    assert result.cash_flows[0].quantity == 10
    assert result.cash_flows[0].amount == 10


def test_additional_buy_on_ex_date_does_not_increase_entitlement() -> None:
    d1, d2, ex_date = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": frame(
            "AAPL", bar(d1, 10, 10), bar(d2, 10, 10), bar(ex_date, 10, 10),
        )},
        {"AAPL": pd.DataFrame([action("AAPL", ex_date, "dividend", dividend=1)])},
    )
    subject = engine(store, cash=200)
    result = subject.run(d1, ex_date, {
        d1: allocation(subject, d1, AAPL=0.5),
        d2: allocation(subject, d2, AAPL=0.75),
    })

    assert result.snapshots[-1].positions[0].quantity == 15
    assert result.cash_flows[0].quantity == 10
    assert result.cash_flows[0].amount == 10


def test_same_day_split_precedes_dividend_entitlement_capture() -> None:
    d1, d2, ex_date = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": frame(
            "AAPL", bar(d1, 100, 100), bar(d2, 100, 100), bar(ex_date, 50, 50),
        )},
        {"AAPL": pd.DataFrame([
            action("AAPL", ex_date, "split", split=2),
            action("AAPL", ex_date, "dividend", dividend=0.5),
        ])},
    )
    subject = engine(store)
    result = subject.run(d1, ex_date, {d1: allocation(subject, d1, AAPL=1)})

    assert result.snapshots[-1].positions[0].quantity == 20
    assert result.cash_flows[0].cash_flow_type == CashFlowType.DIVIDEND
    assert result.cash_flows[0].quantity == 20
    assert result.cash_flows[0].amount == 10
    assert result.snapshots[-1].nav == 1_010


def test_complex_action_on_held_position_invalidates_run_with_context() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    events = pd.DataFrame([{
        "event_id": "evt-merger", "ticker": "AAPL", "event_date": d3,
        "event_type": "merger", "training_exclusion": True,
        "adjustment_supported": False,
    }])
    store = MemoryMarketStore(
        {"AAPL": frame("AAPL", bar(d1, 10, 10), bar(d2, 10, 10), bar(d3, 10, 10))},
        events=events,
    )
    subject = engine(store)
    with pytest.raises(UnmodelledCorporateActionError) as error:
        subject.run(d1, d3, {d1: allocation(subject, d1, AAPL=1)})
    assert error.value.event_id == "evt-merger"
    assert error.value.ticker == "AAPL"


def test_average_cost_realized_and_unrealized_pnl_are_separate() -> None:
    d1, d2, d3 = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore({
        "AAPL": frame("AAPL", bar(d1, 10, 10), bar(d2, 10, 12), bar(d3, 15, 15)),
    })
    subject = engine(store)
    result = subject.run(d1, d3, {
        d1: allocation(subject, d1, AAPL=1),
        d2: allocation(subject, d2, AAPL=0.5),
    })
    sell = [item for item in result.fills if item.side == OrderSide.SELL][0]
    remaining = result.snapshots[-1].positions[0]
    assert sell.quantity == pytest.approx(50)
    assert remaining.average_cost == 10
    assert result.realized_pnl == pytest.approx(250)
    assert result.final_unrealized_pnl == pytest.approx(250)


def test_run_is_deterministic_and_all_timestamps_are_aware() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    store = MemoryMarketStore({"AAPL": frame("AAPL", bar(d1, 10, 10), bar(d2, 10, 10))})
    subject = engine(store)
    allocations = {d1: allocation(subject, d1, AAPL=0.5)}
    first = subject.run(d1, d2, allocations)
    second = subject.run(d1, d2, allocations)
    assert first.model_dump() == second.model_dump()
    assert first.metadata["survivorship_bias_warning"] is True
    timestamps = [
        *(item.generated_at for item in first.allocations),
        *(item.submitted_at for item in first.orders),
        *(item.filled_at for item in first.fills),
        *(item.recorded_at for item in first.executions),
        *(item.as_of for item in first.snapshots),
    ]
    assert all(value.tzinfo is not None and value.utcoffset() is not None for value in timestamps)


def test_invalid_allocation_timing_range_and_empty_run_id_fail_explicitly() -> None:
    d1 = date(2025, 1, 2)
    store = MemoryMarketStore({"AAPL": frame("AAPL", bar(d1, 10, 10))})
    subject = engine(store)
    bad_time = TargetAllocation(
        generated_at=subject.decision_time(d1) - timedelta(minutes=1),
        weights={"AAPL": 0.5}, cash_weight=0.5,
    )
    with pytest.raises(ValueError, match="must equal decision_time"):
        subject.run(d1, d1, {d1: bad_time})
    with pytest.raises(ValueError, match="run_id"):
        subject.run(d1, d1, {}, run_id=" ")
