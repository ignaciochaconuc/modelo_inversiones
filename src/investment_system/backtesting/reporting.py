"""Deterministic economic reporting and an internal SPY benchmark simulation."""
from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

from investment_system.backtesting.engine import BacktestDataError, HistoricalBacktestEngine
from investment_system.backtesting.metrics import nav_series_from_snapshots, performance_metrics
from investment_system.backtesting.schemas import (
    BacktestMetrics, BacktestResult, BenchmarkMetrics, CashFlowType, CostMetrics,
    CorporateActionMetrics, ExecutionMetrics, ExposureMetrics, OrderStatus,
    PerformanceMetrics,
)
from investment_system.backtesting.strategies.base import (
    buy_and_hold_allocations, sessions,
)
from investment_system.data.calendar import TradingCalendar
from investment_system.data.storage.market_store import MarketDataStore


METRICS_VERSION = "backtest-metrics-v2"
SURVIVORSHIP_WARNING = (
    "development_fixed universe is not point-in-time and contains survivorship bias"
)


class BenchmarkDataError(ValueError):
    """The benchmark cannot be simulated reliably for the portfolio range."""


def _market_date(value: datetime, timezone_name: str) -> date:
    return value.astimezone(ZoneInfo(timezone_name)).date()


def calculate_execution_metrics(result: BacktestResult) -> ExecutionMetrics:
    """Summarize one terminal execution record per attempted order."""
    total_records = len(result.executions)
    filled = sum(item.status == OrderStatus.FILLED for item in result.executions)
    partial = sum(item.status == OrderStatus.PARTIALLY_FILLED for item in result.executions)
    unfilled = sum(item.status == OrderStatus.UNFILLED for item in result.executions)
    attempted_ids = {item.order_id for item in result.executions}
    pending = sum(order.order_id not in attempted_ids for order in result.orders)
    denominator = float(total_records)
    return ExecutionMetrics(
        total_orders=len(result.orders),
        total_fills=len(result.fills),
        total_execution_records=total_records,
        filled_orders=filled,
        partially_filled_orders=partial,
        unfilled_orders=unfilled,
        pending_orders=pending,
        fill_rate=None if not total_records else filled / denominator,
        partial_fill_rate=None if not total_records else partial / denominator,
        unfilled_rate=None if not total_records else unfilled / denominator,
    )


def calculate_cost_metrics(
    result: BacktestResult,
    performance: PerformanceMetrics,
) -> CostMetrics:
    """Use executed fill notional; unfilled order notional never contributes."""
    timezone_name = str(result.metadata.get("market_timezone", "America/New_York"))
    nav_by_date = {
        _market_date(snapshot.as_of, timezone_name): snapshot.nav
        for snapshot in result.snapshots
    }
    traded_by_date: dict[date, float] = {}
    for fill in result.fills:
        session = _market_date(fill.filled_at, timezone_name)
        traded_by_date[session] = traded_by_date.get(session, 0.0) + fill.notional
    unknown_dates = sorted(set(traded_by_date) - set(nav_by_date))
    if unknown_dates:
        raise ValueError(f"fills have no matching session snapshot: {unknown_dates}")
    gross_notional = sum(fill.notional for fill in result.fills)
    commissions = sum(fill.commission for fill in result.fills)
    slippage = sum(fill.slippage_cost for fill in result.fills)
    total_cost = commissions + slippage
    daily_turnover = [
        traded_by_date.get(session, 0.0) / nav
        for session, nav in sorted(nav_by_date.items())
    ]
    total_turnover = sum(daily_turnover)
    average_turnover = total_turnover / len(daily_turnover)
    return CostMetrics(
        gross_traded_notional=gross_notional,
        total_commissions=commissions,
        total_slippage_cost=slippage,
        total_transaction_cost=total_cost,
        cost_over_initial_nav=total_cost / performance.initial_nav,
        cost_over_traded_notional=(
            None if gross_notional == 0 else total_cost / gross_notional
        ),
        total_turnover=total_turnover,
        average_daily_turnover=average_turnover,
        annualized_turnover=average_turnover * 252,
    )


def calculate_exposure_metrics(result: BacktestResult) -> ExposureMetrics:
    if not result.snapshots:
        raise ValueError("at least one portfolio snapshot is required")
    count = len(result.snapshots)
    cash_weights = [snapshot.cash_weight for snapshot in result.snapshots]
    position_counts = [len(snapshot.positions) for snapshot in result.snapshots]
    return ExposureMetrics(
        average_gross_exposure=sum(item.gross_exposure for item in result.snapshots) / count,
        average_net_exposure=sum(item.net_exposure for item in result.snapshots) / count,
        average_cash_weight=sum(cash_weights) / count,
        minimum_cash_weight=min(cash_weights),
        maximum_cash_weight=max(cash_weights),
        maximum_positions=max(position_counts),
        average_positions=sum(position_counts) / count,
    )


def calculate_corporate_action_metrics(result: BacktestResult) -> CorporateActionMetrics:
    dividends = [
        flow for flow in result.cash_flows
        if flow.cash_flow_type == CashFlowType.DIVIDEND
    ]
    cash_in_lieu = [
        flow for flow in result.cash_flows
        if flow.cash_flow_type == CashFlowType.CASH_IN_LIEU
    ]
    recapitalization = [
        flow for flow in result.cash_flows
        if flow.cash_flow_type == CashFlowType.RECAPITALIZATION_CASH
    ]
    return CorporateActionMetrics(
        dividend_cash=sum(flow.amount for flow in dividends),
        dividend_cash_flow_count=len(dividends),
        cash_in_lieu=sum(flow.amount for flow in cash_in_lieu),
        cash_in_lieu_count=len(cash_in_lieu),
        recapitalization_cash=sum(flow.amount for flow in recapitalization),
        recapitalization_cash_flow_count=len(recapitalization),
        reviewed_transformation_count=len(result.corporate_action_transformations),
    )


def simulate_benchmark(
    result: BacktestResult,
    market_store: MarketDataStore,
    calendar: TradingCalendar,
) -> BacktestResult:
    """Simulate benchmark buy-and-hold with causal next-open dividend reinvestment."""
    if not result.snapshots:
        raise BenchmarkDataError("portfolio result has no snapshots")
    timezone_name = str(result.metadata.get("market_timezone", "America/New_York"))
    start = _market_date(result.snapshots[0].as_of, timezone_name)
    end = _market_date(result.snapshots[-1].as_of, timezone_name)
    trading_sessions = sessions(start, end, calendar)
    if len(trading_sessions) < 2:
        raise BenchmarkDataError("benchmark requires at least two sessions for next-open entry")

    cutoff = str(result.metadata.get("decision_cutoff", "20:15"))
    subject = HistoricalBacktestEngine(
        result.config,
        market_store,
        calendar,
        market_timezone=timezone_name,
        decision_cutoff=cutoff,
    )
    ticker = result.config.benchmark_ticker
    allocations = buy_and_hold_allocations(
        ticker=ticker,
        start=start,
        end=end,
        calendar=calendar,
        actions=market_store.read_actions(ticker),
        timezone_name=timezone_name,
        cutoff=cutoff,
    )
    try:
        benchmark = subject.run(
            start,
            end,
            allocations,
            run_id=f"{result.run_id}:benchmark:{ticker}:{METRICS_VERSION}",
        )
    except (BacktestDataError, ValueError) as error:
        raise BenchmarkDataError(f"cannot simulate {ticker} benchmark: {error}") from error

    initial_order = benchmark.orders[0] if benchmark.orders else None
    initial_execution = next(
        (
            execution for execution in benchmark.executions
            if initial_order is not None and execution.order_id == initial_order.order_id
        ),
        None,
    )
    if initial_execution is None or initial_execution.status == OrderStatus.UNFILLED:
        reason = None if initial_execution is None else initial_execution.reason
        raise BenchmarkDataError(
            f"cannot establish {ticker} benchmark position: {reason or 'no execution'}"
        )
    portfolio_dates = [
        _market_date(snapshot.as_of, timezone_name) for snapshot in result.snapshots
    ]
    benchmark_dates = [
        _market_date(snapshot.as_of, timezone_name) for snapshot in benchmark.snapshots
    ]
    if benchmark_dates != portfolio_dates:
        raise BenchmarkDataError("benchmark and portfolio session ranges do not match")
    return benchmark


def _report_warnings(result: BacktestResult, benchmark: BacktestResult | None) -> list[str]:
    warnings: list[str] = []
    if bool(result.metadata.get("survivorship_bias_warning")):
        warnings.append(SURVIVORSHIP_WARNING)
    if any(snapshot.stale_price_tickers for snapshot in result.snapshots):
        warnings.append("portfolio contains explicitly marked stale valuation prices")
    if benchmark and any(snapshot.stale_price_tickers for snapshot in benchmark.snapshots):
        warnings.append("benchmark contains explicitly marked stale valuation prices")
    if result.pnl_incomplete_tickers:
        warnings.append(
            "trading P&L is unavailable because reviewed spin-off holdings have "
            "unallocated cost basis; NAV performance remains complete"
        )
    return warnings


def build_backtest_report(
    result: BacktestResult,
    *,
    benchmark_result: BacktestResult | None = None,
    market_store: MarketDataStore | None = None,
    calendar: TradingCalendar | None = None,
) -> BacktestMetrics:
    """Build a stable report; benchmark construction is explicit and has no writes."""
    if (market_store is None) != (calendar is None):
        raise ValueError("market_store and calendar must be provided together")
    if benchmark_result is not None and market_store is not None:
        raise ValueError("provide benchmark_result or benchmark inputs, not both")
    benchmark = benchmark_result
    if market_store is not None and calendar is not None:
        benchmark = simulate_benchmark(result, market_store, calendar)

    performance = performance_metrics(nav_series_from_snapshots(result.snapshots))
    costs = calculate_cost_metrics(result, performance)
    benchmark_metrics = None
    if benchmark is not None:
        if benchmark.config != result.config:
            raise BenchmarkDataError(
                "benchmark must use the same backtest configuration and costs"
            )
        benchmark_performance = performance_metrics(
            nav_series_from_snapshots(benchmark.snapshots),
        )
        if (
            benchmark_performance.start_date != performance.start_date
            or benchmark_performance.end_date != performance.end_date
            or benchmark_performance.session_count != performance.session_count
        ):
            raise BenchmarkDataError("benchmark and portfolio metric ranges do not match")
        if benchmark_performance.initial_nav != performance.initial_nav:
            raise BenchmarkDataError("benchmark and portfolio initial NAV do not match")
        benchmark_costs = calculate_cost_metrics(benchmark, benchmark_performance)
        excess_cagr = (
            None
            if performance.cagr is None or benchmark_performance.cagr is None
            else performance.cagr - benchmark_performance.cagr
        )
        excess_return = (
            performance.cumulative_return - benchmark_performance.cumulative_return
        )
        benchmark_metrics = BenchmarkMetrics(
            ticker=result.config.benchmark_ticker,
            run_id=benchmark.run_id,
            performance=benchmark_performance,
            costs=benchmark_costs,
            excess_cumulative_return=excess_return,
            excess_cagr=excess_cagr,
            tracking_difference=excess_return,
        )

    return BacktestMetrics(
        metrics_version=METRICS_VERSION,
        run_id=result.run_id,
        backtest_config=result.config.model_dump(mode="json"),
        performance=performance,
        execution=calculate_execution_metrics(result),
        costs=costs,
        exposure=calculate_exposure_metrics(result),
        corporate_actions=calculate_corporate_action_metrics(result),
        realized_pnl=result.realized_pnl,
        final_unrealized_pnl=result.final_unrealized_pnl,
        total_trading_pnl=(
            None
            if result.pnl_incomplete_tickers
            else result.realized_pnl + result.final_unrealized_pnl
        ),
        trading_pnl_complete=not result.pnl_incomplete_tickers,
        unknown_cost_basis_tickers=result.pnl_incomplete_tickers,
        benchmark=benchmark_metrics,
        warnings=_report_warnings(result, benchmark),
    )
