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
from investment_system.backtesting.strategies import (
    BaselineStrategy, EqualWeightStrategy, SimpleMomentumStrategy,
    SpyBuyAndHoldStrategy, StrategyPlan,
)

__all__ = [
    "BacktestConfig", "BacktestDataError", "BacktestMetrics", "BacktestPosition",
    "BacktestResult", "BaselineStrategy", "BaseBacktestEngine", "BenchmarkDataError",
    "BenchmarkMetrics", "CashFlowType", "CorporateActionCashFlow",
    "CorporateActionMetrics", "CostMetrics", "ExecutionMetrics",
    "EqualWeightStrategy", "ExposureMetrics", "HistoricalBacktestEngine",
    "METRICS_VERSION",
    "OrderExecutionRecord", "OrderSide", "OrderStatus", "PerformanceMetrics",
    "PortfolioLedger", "PortfolioSnapshot", "SimpleMomentumStrategy",
    "SimulatedFill", "SimulatedOrder", "SpyBuyAndHoldStrategy", "StrategyPlan",
    "TargetAllocation", "UnmodelledCorporateActionError",
    "build_backtest_report", "simulate_benchmark",
]
