"""Backtesting contracts and deterministic historical portfolio accounting."""

from investment_system.backtesting.engine import (
    BacktestDataError, BaseBacktestEngine, HistoricalBacktestEngine,
    UnmodelledCorporateActionError,
)
from investment_system.backtesting.portfolio import PortfolioLedger
from investment_system.backtesting.corporate_actions import (
    CostBasisPolicy, DistributedSecurity, EntitlementTiming, FractionalDistributionPolicy,
    ProviderActionType, RecapitalizationCashAndSplitTreatment,
    ReviewedCorporateActionTreatments, SecurityDistributionTreatment,
    load_reviewed_corporate_action_treatments,
)
from investment_system.backtesting.reporting import (
    BenchmarkDataError, METRICS_VERSION, build_backtest_report, simulate_benchmark,
)
from investment_system.backtesting.schemas import (
    BacktestConfig, BacktestMetrics, BacktestPosition, BacktestResult,
    BenchmarkMetrics, CashFlowType, CorporateActionCashFlow,
    CorporateActionMetrics, CorporateActionTransformation, CostBasisStatus,
    CostMetrics, ExecutionMetrics, ExposureMetrics,
    DistributedSecurityTransformation,
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
    "CorporateActionMetrics", "CorporateActionTransformation", "CostBasisPolicy",
    "CostBasisStatus", "CostMetrics", "EntitlementTiming", "ExecutionMetrics",
    "EqualWeightStrategy", "ExposureMetrics", "HistoricalBacktestEngine",
    "METRICS_VERSION",
    "FractionalDistributionPolicy", "OrderExecutionRecord", "OrderSide",
    "OrderStatus", "PerformanceMetrics", "ProviderActionType",
    "PortfolioLedger", "PortfolioSnapshot", "SimpleMomentumStrategy",
    "SimulatedFill", "SimulatedOrder", "SpyBuyAndHoldStrategy", "StrategyPlan",
    "RecapitalizationCashAndSplitTreatment", "ReviewedCorporateActionTreatments",
    "DistributedSecurity", "DistributedSecurityTransformation",
    "SecurityDistributionTreatment", "TargetAllocation",
    "UnmodelledCorporateActionError", "build_backtest_report",
    "load_reviewed_corporate_action_treatments", "simulate_benchmark",
]
