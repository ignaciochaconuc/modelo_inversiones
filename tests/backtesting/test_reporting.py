from __future__ import annotations

from datetime import date, datetime
import json
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from investment_system.backtesting import (
    BacktestConfig, BacktestPosition, BacktestResult, BenchmarkDataError,
    CashFlowType, CorporateActionCashFlow, OrderExecutionRecord, OrderSide,
    OrderStatus, PortfolioSnapshot, SimulatedFill, SimulatedOrder,
    build_backtest_report, simulate_benchmark,
)
from investment_system.backtesting.reporting import (
    METRICS_VERSION, SURVIVORSHIP_WARNING, calculate_corporate_action_metrics,
    calculate_cost_metrics, calculate_execution_metrics, calculate_exposure_metrics,
)
from investment_system.backtesting.metrics import nav_series_from_snapshots, performance_metrics
from investment_system.data.calendar import XNYSTradingCalendar


NY = ZoneInfo("America/New_York")


class MemoryMarketStore:
    def __init__(
        self,
        bars: dict[str, pd.DataFrame],
        actions: dict[str, pd.DataFrame] | None = None,
    ) -> None:
        self.bars = bars
        self.actions = actions or {}

    def read_bars(self, ticker: str) -> pd.DataFrame:
        return self.bars.get(ticker, pd.DataFrame()).copy()

    def read_actions(self, ticker: str) -> pd.DataFrame:
        return self.actions.get(ticker, pd.DataFrame()).copy()

    def read_corporate_action_events(self) -> pd.DataFrame:
        return pd.DataFrame()


def bar(day: date, open_: float, close: float, *, available_hour: int = 20) -> dict:
    return {
        "ticker": "SPY", "trading_date": day, "open": open_, "close": close,
        "available_at": datetime(day.year, day.month, day.day, available_hour, tzinfo=NY),
    }


def bars(*rows: dict) -> pd.DataFrame:
    return pd.DataFrame(rows)


def action(day: date, kind: str, *, split: float | None = None,
           dividend: float | None = None) -> dict:
    return {
        "ticker": "SPY", "effective_date": day, "action_type": kind,
        "split_factor": split, "dividend_cash": dividend,
    }


def snapshot(
    day: date,
    *,
    cash: float,
    positions: list[BacktestPosition] | None = None,
) -> PortfolioSnapshot:
    held = positions or []
    market_value = sum(position.market_value for position in held)
    nav = cash + market_value
    return PortfolioSnapshot(
        as_of=datetime(day.year, day.month, day.day, 20, 15, tzinfo=NY),
        cash=cash,
        positions=held,
        gross_exposure=market_value / nav,
        net_exposure=market_value / nav,
        market_value=market_value,
        nav=nav,
        weights={position.ticker: position.market_value / nav for position in held},
        cash_weight=cash / nav,
    )


def result_with_snapshots(
    *snapshots: PortfolioSnapshot,
    config: BacktestConfig | None = None,
    **updates,
) -> BacktestResult:
    return BacktestResult(
        run_id="portfolio-run",
        config=config or BacktestConfig(initial_cash=snapshots[0].nav),
        snapshots=list(snapshots),
        metadata={
            "market_timezone": "America/New_York",
            "decision_cutoff": "20:15",
            "survivorship_bias_warning": True,
        },
        **updates,
    )


def cash_result(days: list[date], *, cash: float = 1_000) -> BacktestResult:
    return result_with_snapshots(*(snapshot(day, cash=cash) for day in days))


def test_execution_cost_and_fill_notional_turnover_metrics() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    order_one = SimulatedOrder(
        order_id="order-1", allocation_id="allocation-1", ticker="AAPL",
        side=OrderSide.BUY, quantity=20,
        submitted_at=datetime(2025, 1, 2, 20, 15, tzinfo=NY),
        execution_date=d2, target_weight=0.2, reference_price=10,
    )
    order_two = order_one.model_copy(update={"order_id": "order-2", "ticker": "MSFT"})
    fill = SimulatedFill(
        fill_id="fill-1", order_id="order-1", allocation_id="allocation-1",
        ticker="AAPL", side=OrderSide.BUY, quantity=10,
        raw_open_price=9.8, fill_price=10, notional=100,
        commission=1, slippage_cost=2,
        filled_at=datetime(2025, 1, 3, 9, 30, tzinfo=NY),
    )
    executions = [
        OrderExecutionRecord(
            order_id="order-1", allocation_id="allocation-1", ticker="AAPL",
            execution_date=d2, status=OrderStatus.PARTIALLY_FILLED,
            requested_quantity=20, filled_quantity=10, quantity_reduced=True,
            recorded_at=datetime(2025, 1, 3, 9, 30, tzinfo=NY),
        ),
        OrderExecutionRecord(
            order_id="order-2", allocation_id="allocation-1", ticker="MSFT",
            execution_date=d2, status=OrderStatus.UNFILLED,
            requested_quantity=20, reason="missing_execution_open",
            recorded_at=datetime(2025, 1, 3, 9, 30, tzinfo=NY),
        ),
    ]
    held = BacktestPosition(ticker="AAPL", quantity=10, average_cost=10, market_price=10)
    result = result_with_snapshots(
        snapshot(d1, cash=1_000), snapshot(d2, cash=900, positions=[held]),
        orders=[order_one, order_two], fills=[fill], executions=executions,
    )
    performance = performance_metrics(nav_series_from_snapshots(result.snapshots))
    execution = calculate_execution_metrics(result)
    costs = calculate_cost_metrics(result, performance)

    assert execution.total_orders == 2
    assert execution.total_fills == 1
    assert execution.partially_filled_orders == 1
    assert execution.unfilled_orders == 1
    assert execution.partial_fill_rate == execution.unfilled_rate == 0.5
    assert costs.gross_traded_notional == 100
    assert costs.total_commissions == 1
    assert costs.total_slippage_cost == 2
    assert costs.total_transaction_cost == 3
    assert costs.cost_over_initial_nav == pytest.approx(0.003)
    assert costs.cost_over_traded_notional == pytest.approx(0.03)
    assert costs.total_turnover == pytest.approx(0.1)
    assert costs.average_daily_turnover == pytest.approx(0.05)
    assert costs.annualized_turnover == pytest.approx(12.6)


def test_pending_and_unfilled_orders_never_create_turnover() -> None:
    d1 = date(2025, 1, 2)
    order = SimulatedOrder(
        order_id="pending", allocation_id="allocation", ticker="AAPL",
        side=OrderSide.BUY, quantity=10,
        submitted_at=datetime(2025, 1, 2, 20, 15, tzinfo=NY),
        execution_date=date(2025, 1, 3), target_weight=1, reference_price=10,
    )
    result = result_with_snapshots(snapshot(d1, cash=100), orders=[order])
    report = build_backtest_report(result)
    assert report.execution.pending_orders == 1
    assert report.execution.fill_rate is None
    assert report.costs.gross_traded_notional == 0
    assert report.costs.total_turnover == 0
    assert report.costs.cost_over_traded_notional is None


def test_exposure_statistics_cover_cash_only_and_fully_invested_sessions() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    held = BacktestPosition(ticker="AAPL", quantity=10, average_cost=10, market_price=10)
    result = result_with_snapshots(
        snapshot(d1, cash=100), snapshot(d2, cash=0, positions=[held]),
    )
    metrics = calculate_exposure_metrics(result)
    assert metrics.average_cash_weight == 0.5
    assert metrics.minimum_cash_weight == 0
    assert metrics.maximum_cash_weight == 1
    assert metrics.average_gross_exposure == metrics.average_net_exposure == 0.5
    assert metrics.maximum_positions == 1
    assert metrics.average_positions == 0.5


def test_corporate_action_cash_is_separate_and_defaults_to_zero() -> None:
    day = date(2025, 1, 2)
    empty = cash_result([day])
    assert calculate_corporate_action_metrics(empty).model_dump() == {
        "dividend_cash": 0.0, "dividend_cash_flow_count": 0,
        "cash_in_lieu": 0.0, "cash_in_lieu_count": 0,
    }
    flows = [
        CorporateActionCashFlow(
            cash_flow_id="dividend", ticker="AAPL",
            cash_flow_type=CashFlowType.DIVIDEND, effective_date=day,
            quantity=10, amount_per_share=2, amount=20,
            occurred_at=datetime(2025, 1, 2, 16, tzinfo=NY),
        ),
        CorporateActionCashFlow(
            cash_flow_id="cil", ticker="AAPL",
            cash_flow_type=CashFlowType.CASH_IN_LIEU, effective_date=day,
            quantity=0.5, amount_per_share=10, amount=5,
            occurred_at=datetime(2025, 1, 2, 9, 30, tzinfo=NY),
        ),
    ]
    metrics = calculate_corporate_action_metrics(
        result_with_snapshots(snapshot(day, cash=100), cash_flows=flows),
    )
    assert metrics.dividend_cash == 20
    assert metrics.dividend_cash_flow_count == 1
    assert metrics.cash_in_lieu == 5
    assert metrics.cash_in_lieu_count == 1


def test_report_is_deterministic_json_serializable_and_preserves_metadata() -> None:
    days = [date(2025, 1, 2), date(2025, 1, 3)]
    result = cash_result(days)
    first = build_backtest_report(result)
    second = build_backtest_report(result)
    assert first == second
    assert json.loads(first.model_dump_json())["run_id"] == "portfolio-run"
    assert first.metrics_version == METRICS_VERSION
    assert first.warnings == [SURVIVORSHIP_WARNING]
    assert first.total_trading_pnl == 0


def test_report_keeps_accounting_pnl_separate_from_dividend_cash() -> None:
    day = date(2025, 1, 2)
    dividend = CorporateActionCashFlow(
        cash_flow_id="dividend", ticker="AAPL",
        cash_flow_type=CashFlowType.DIVIDEND, effective_date=day,
        quantity=10, amount_per_share=2, amount=20,
        occurred_at=datetime(2025, 1, 2, 16, tzinfo=NY),
    )
    result = result_with_snapshots(
        snapshot(day, cash=120), cash_flows=[dividend],
        realized_pnl=7, final_unrealized_pnl=3,
    )
    report = build_backtest_report(result)
    assert report.realized_pnl == 7
    assert report.final_unrealized_pnl == 3
    assert report.total_trading_pnl == 10
    assert report.corporate_actions.dividend_cash == 20


def test_flat_spy_benchmark_has_zero_return_matching_cash_portfolio() -> None:
    days = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
    store = MemoryMarketStore({"SPY": bars(*(bar(day, 100, 100) for day in days))})
    portfolio = cash_result(days)
    benchmark = simulate_benchmark(portfolio, store, XNYSTradingCalendar())
    report = build_backtest_report(portfolio, benchmark_result=benchmark)
    execution = calculate_execution_metrics(benchmark)
    assert execution.filled_orders == 1
    assert execution.fill_rate == 1
    assert report.benchmark.performance.cumulative_return == 0
    assert report.benchmark.excess_cumulative_return == 0
    assert report.benchmark.tracking_difference == 0
    assert report.benchmark.performance.start_date == report.performance.start_date
    assert report.benchmark.performance.end_date == report.performance.end_date
    assert report.benchmark.performance.session_count == report.performance.session_count


def test_spy_price_double_uses_raw_not_adjusted_prices() -> None:
    days = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
    frame = bars(bar(days[0], 100, 100), bar(days[1], 100, 100), bar(days[2], 200, 200))
    frame["adjusted_open"] = [1, 1, 1]
    frame["adjusted_close"] = [1, 1, 1]
    benchmark = simulate_benchmark(
        cash_result(days), MemoryMarketStore({"SPY": frame}), XNYSTradingCalendar(),
    )
    report = build_backtest_report(cash_result(days), benchmark_result=benchmark)
    assert report.benchmark.performance.cumulative_return == pytest.approx(1)
    assert report.benchmark.performance.final_nav == pytest.approx(2_000)


def test_spy_dividend_increases_value_and_reinvests_next_open() -> None:
    days = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6), date(2025, 1, 7)]
    store = MemoryMarketStore(
        {"SPY": bars(*(bar(day, 100, 100) for day in days))},
        {"SPY": pd.DataFrame([action(days[2], "dividend", dividend=1)])},
    )
    benchmark = simulate_benchmark(cash_result(days), store, XNYSTradingCalendar())
    report = build_backtest_report(cash_result(days), benchmark_result=benchmark)
    assert benchmark.cash_flows[0].quantity == 10
    assert benchmark.cash_flows[0].amount == 10
    assert len(benchmark.fills) == 2
    assert benchmark.fills[1].filled_at.date() == days[3]
    assert report.benchmark.performance.final_nav == pytest.approx(1_010)
    assert report.benchmark.performance.cumulative_return == pytest.approx(0.01)


def test_spy_buy_on_ex_date_has_no_dividend_entitlement() -> None:
    days = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
    store = MemoryMarketStore(
        {"SPY": bars(*(bar(day, 100, 100) for day in days))},
        {"SPY": pd.DataFrame([action(days[1], "dividend", dividend=1)])},
    )
    benchmark = simulate_benchmark(cash_result(days), store, XNYSTradingCalendar())
    assert benchmark.fills[0].filled_at.date() == days[1]
    assert benchmark.cash_flows == []
    assert benchmark.snapshots[-1].nav == 1_000


def test_spy_split_preserves_benchmark_economic_value() -> None:
    days = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
    store = MemoryMarketStore(
        {"SPY": bars(bar(days[0], 100, 100), bar(days[1], 100, 100), bar(days[2], 50, 50))},
        {"SPY": pd.DataFrame([action(days[2], "split", split=2)])},
    )
    benchmark = simulate_benchmark(cash_result(days), store, XNYSTradingCalendar())
    assert benchmark.snapshots[-1].positions[0].quantity == 20
    assert benchmark.snapshots[-1].nav == 1_000


@pytest.mark.parametrize("failure", ["late_first_close", "missing_entry_open"])
def test_benchmark_fails_on_unreliable_or_future_data(failure: str) -> None:
    days = [date(2025, 1, 2), date(2025, 1, 3)]
    if failure == "late_first_close":
        frame = bars(bar(days[0], 100, 100, available_hour=21), bar(days[1], 100, 100))
    else:
        frame = bars(bar(days[0], 100, 100))
    with pytest.raises(BenchmarkDataError):
        simulate_benchmark(
            cash_result(days), MemoryMarketStore({"SPY": frame}), XNYSTradingCalendar(),
        )
