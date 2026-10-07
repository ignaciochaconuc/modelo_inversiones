"""Backtesting contracts and deterministic historical portfolio accounting."""

from investment_system.backtesting.engine import (
    BacktestDataError, BaseBacktestEngine, HistoricalBacktestEngine,
    UnmodelledCorporateActionError,
)
from investment_system.backtesting.portfolio import PortfolioLedger
from investment_system.backtesting.reporting import (
    BenchmarkDataError, METRICS_VERSION, build_backtest_report, simulate_benchmark,
)
from investment_system.backtesting.schemas import (
    BacktestConfig, BacktestMetrics, BacktestPosition, BacktestResult,
    BenchmarkMetrics, CashFlowType, CorporateActionCashFlow,
    CorporateActionMetrics, CostMetrics, ExecutionMetrics, ExposureMetrics,
    OrderExecutionRecord, OrderSide, OrderStatus, PerformanceMetrics,
    PortfolioSnapshot, SimulatedFill, SimulatedOrder, TargetAllocation,
)

__all__ = [
    "BacktestConfig", "BacktestDataError", "BacktestMetrics", "BacktestPosition",
    "BacktestResult", "BaseBacktestEngine", "BenchmarkDataError",
    "BenchmarkMetrics", "CashFlowType", "CorporateActionCashFlow",
    "CorporateActionMetrics", "CostMetrics", "ExecutionMetrics",
    "ExposureMetrics", "HistoricalBacktestEngine", "METRICS_VERSION",
    "OrderExecutionRecord", "OrderSide", "OrderStatus", "PerformanceMetrics",
    "PortfolioLedger", "PortfolioSnapshot", "SimulatedFill", "SimulatedOrder",
    "TargetAllocation", "UnmodelledCorporateActionError",
    "build_backtest_report", "simulate_benchmark",
]
