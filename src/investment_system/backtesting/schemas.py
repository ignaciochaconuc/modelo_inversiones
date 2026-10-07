"""Backtest-only contracts for historical orders, fills, and portfolio state."""
from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
import math
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator


WEIGHT_TOLERANCE = 1e-9
VALUE_TOLERANCE = 1e-9


def _aware(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


def _ticker(value: str) -> str:
    normalized = value.strip().upper()
    if not normalized or any(character not in "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789.-" for character in normalized):
        raise ValueError("invalid ticker")
    return normalized


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class OrderStatus(StrEnum):
    FILLED = "FILLED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    UNFILLED = "UNFILLED"


class CashFlowType(StrEnum):
    DIVIDEND = "DIVIDEND"
    CASH_IN_LIEU = "CASH_IN_LIEU"
    RECAPITALIZATION_CASH = "RECAPITALIZATION_CASH"


class CostBasisStatus(StrEnum):
    """Whether average cost is known for trading-P&L accounting."""

    KNOWN = "KNOWN"
    UNALLOCATED = "UNALLOCATED"


class BacktestConfig(BaseModel):
    """Simulator-specific settings; global market timing stays in Settings."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    initial_cash: float = Field(gt=0)
    commission_bps: float = Field(default=0, ge=0, lt=10_000)
    slippage_bps: float = Field(default=0, ge=0, lt=10_000)
    allow_fractional_shares: bool = True
    benchmark_ticker: str = "SPY"

    _normalize_benchmark = field_validator("benchmark_ticker")(_ticker)


class BacktestPosition(BaseModel):
    """Long-only position in real units; market value is always derived."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    ticker: str
    quantity: float = Field(gt=0)
    average_cost: float | None = Field(default=None, gt=0)
    market_price: float = Field(gt=0)
    cost_basis_status: CostBasisStatus = CostBasisStatus.KNOWN

    _normalize_ticker = field_validator("ticker")(_ticker)

    @computed_field
    @property
    def market_value(self) -> float:
        return self.quantity * self.market_price

    @model_validator(mode="after")
    def validate_cost_basis(self) -> "BacktestPosition":
        if self.cost_basis_status == CostBasisStatus.KNOWN and self.average_cost is None:
            raise ValueError("KNOWN cost basis requires average_cost")
        if self.cost_basis_status == CostBasisStatus.UNALLOCATED and self.average_cost is not None:
            raise ValueError("UNALLOCATED cost basis must not invent average_cost")
        return self


class TargetAllocation(BaseModel):
    """Target weights produced upstream; this is not an executable order."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    generated_at: datetime
    weights: dict[str, float] = Field(default_factory=dict)
    cash_weight: float = Field(ge=0, le=1)
    allocation_id: str | None = None
    risk_decision_id: str | None = None

    _validate_generated_at = field_validator("generated_at")(_aware)

    @field_validator("weights")
    @classmethod
    def validate_weights(cls, weights: dict[str, float]) -> dict[str, float]:
        normalized: dict[str, float] = {}
        for ticker, weight in weights.items():
            name = _ticker(ticker)
            if name in normalized:
                raise ValueError("duplicate ticker after normalization")
            if not math.isfinite(weight) or weight < 0 or weight > 1:
                raise ValueError("target weights must be finite and within [0, 1]")
            normalized[name] = weight
        return normalized

    @model_validator(mode="after")
    def validate_total_weight(self) -> "TargetAllocation":
        if not math.isclose(sum(self.weights.values()) + self.cash_weight, 1.0, abs_tol=WEIGHT_TOLERANCE):
            raise ValueError("asset weights plus cash_weight must equal 1")
        return self


class SimulatedOrder(BaseModel):
    """Historical order created after a decision; a future engine may fill it only next-session-open."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    order_id: str = Field(min_length=1)
    allocation_id: str = Field(min_length=1)
    risk_decision_id: str | None = None
    ticker: str
    side: OrderSide
    quantity: float = Field(gt=0)
    submitted_at: datetime
    execution_date: date
    target_weight: float = Field(ge=0, le=1)
    reference_price: float = Field(gt=0)

    _normalize_ticker = field_validator("ticker")(_ticker)
    _validate_submitted_at = field_validator("submitted_at")(_aware)


class SimulatedFill(BaseModel):
    """A simulated execution priced from the raw next-session opening price."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    fill_id: str = Field(min_length=1)
    order_id: str = Field(min_length=1)
    allocation_id: str = Field(min_length=1)
    ticker: str
    side: OrderSide
    quantity: float = Field(gt=0)
    raw_open_price: float = Field(gt=0)
    fill_price: float = Field(gt=0)
    notional: float = Field(gt=0)
    commission: float = Field(default=0, ge=0)
    slippage_cost: float = Field(default=0, ge=0)
    filled_at: datetime

    _normalize_ticker = field_validator("ticker")(_ticker)
    _validate_filled_at = field_validator("filled_at")(_aware)

    @model_validator(mode="after")
    def validate_economics(self) -> "SimulatedFill":
        expected_notional = self.quantity * self.fill_price
        if not math.isclose(self.notional, expected_notional, rel_tol=1e-12, abs_tol=VALUE_TOLERANCE):
            raise ValueError("notional must equal quantity * fill_price")
        expected_slippage = abs(self.fill_price - self.raw_open_price) * self.quantity
        if not math.isclose(self.slippage_cost, expected_slippage, rel_tol=1e-12, abs_tol=VALUE_TOLERANCE):
            raise ValueError("slippage_cost must equal abs(fill_price - raw_open_price) * quantity")
        return self


class PortfolioSnapshot(BaseModel):
    """Immutable marked-to-market state; exposures and weights are fractions of NAV."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    as_of: datetime
    cash: float = Field(ge=0)
    positions: list[BacktestPosition] = Field(default_factory=list)
    gross_exposure: float = Field(ge=0)
    net_exposure: float = Field(ge=0)
    market_value: float = Field(ge=0)
    nav: float = Field(ge=0)
    weights: dict[str, float] = Field(default_factory=dict)
    cash_weight: float = Field(ge=0, le=1)
    stale_price_tickers: list[str] = Field(default_factory=list)
    unknown_cost_basis_tickers: list[str] = Field(default_factory=list)
    realized_pnl: float = 0
    unrealized_pnl: float = 0

    _validate_as_of = field_validator("as_of")(_aware)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "PortfolioSnapshot":
        tickers = [position.ticker for position in self.positions]
        if len(tickers) != len(set(tickers)):
            raise ValueError("snapshot contains duplicate positions")
        if not set(self.stale_price_tickers).issubset(tickers):
            raise ValueError("stale prices may reference only held positions")
        expected_unknown = sorted(
            position.ticker for position in self.positions
            if position.cost_basis_status == CostBasisStatus.UNALLOCATED
        )
        if sorted(self.unknown_cost_basis_tickers) != expected_unknown:
            raise ValueError("unknown cost-basis tickers must match held positions")
        expected_market_value = sum(position.market_value for position in self.positions)
        if not math.isclose(self.market_value, expected_market_value, abs_tol=VALUE_TOLERANCE):
            raise ValueError("market_value must equal the sum of position values")
        if not math.isclose(self.nav, self.cash + self.market_value, abs_tol=VALUE_TOLERANCE):
            raise ValueError("nav must equal cash + market_value")
        if self.nav > VALUE_TOLERANCE:
            if set(self.weights) != set(tickers):
                raise ValueError("snapshot weights must match position tickers")
            if not math.isclose(sum(self.weights.values()) + self.cash_weight, 1.0, abs_tol=WEIGHT_TOLERANCE):
                raise ValueError("snapshot weights plus cash_weight must equal 1")
            if not math.isclose(self.cash_weight, self.cash / self.nav, abs_tol=WEIGHT_TOLERANCE):
                raise ValueError("cash_weight is inconsistent with cash and NAV")
            for position in self.positions:
                if not math.isclose(
                    self.weights[position.ticker], position.market_value / self.nav,
                    abs_tol=WEIGHT_TOLERANCE,
                ):
                    raise ValueError(f"weight is inconsistent for {position.ticker}")
            expected_exposure = self.market_value / self.nav
            if not math.isclose(self.gross_exposure, expected_exposure, abs_tol=WEIGHT_TOLERANCE):
                raise ValueError("gross_exposure is inconsistent with market value")
            if not math.isclose(self.net_exposure, expected_exposure, abs_tol=WEIGHT_TOLERANCE):
                raise ValueError("net_exposure is inconsistent with long-only positions")
        return self


class OrderExecutionRecord(BaseModel):
    """Auditable outcome for one order on its one permitted execution session."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    order_id: str = Field(min_length=1)
    allocation_id: str = Field(min_length=1)
    ticker: str
    execution_date: date
    status: OrderStatus
    requested_quantity: float = Field(gt=0)
    filled_quantity: float = Field(default=0, ge=0)
    reason: str | None = None
    quantity_reduced: bool = False
    recorded_at: datetime

    _normalize_ticker = field_validator("ticker")(_ticker)
    _validate_recorded_at = field_validator("recorded_at")(_aware)

    @model_validator(mode="after")
    def validate_execution(self) -> "OrderExecutionRecord":
        if self.filled_quantity > self.requested_quantity + VALUE_TOLERANCE:
            raise ValueError("filled quantity cannot exceed requested quantity")
        if self.status == OrderStatus.FILLED and not math.isclose(
            self.filled_quantity, self.requested_quantity, abs_tol=VALUE_TOLERANCE,
        ):
            raise ValueError("FILLED requires the complete requested quantity")
        if self.status == OrderStatus.PARTIALLY_FILLED and not (
            VALUE_TOLERANCE < self.filled_quantity < self.requested_quantity - VALUE_TOLERANCE
        ):
            raise ValueError("PARTIALLY_FILLED requires a partial positive quantity")
        if self.status == OrderStatus.UNFILLED and self.filled_quantity > VALUE_TOLERANCE:
            raise ValueError("UNFILLED requires zero filled quantity")
        return self


class CorporateActionCashFlow(BaseModel):
    """Explicit cash movement caused by a dividend or fractional split settlement."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    cash_flow_id: str = Field(min_length=1)
    event_id: str | None = None
    ticker: str
    cash_flow_type: CashFlowType
    effective_date: date
    quantity: float = Field(ge=0)
    amount_per_share: float = Field(ge=0)
    amount: float = Field(ge=0)
    occurred_at: datetime
    notes: str = ""

    _normalize_ticker = field_validator("ticker")(_ticker)
    _validate_occurred_at = field_validator("occurred_at")(_aware)

    @model_validator(mode="after")
    def validate_amount(self) -> "CorporateActionCashFlow":
        if not math.isclose(self.amount, self.quantity * self.amount_per_share, abs_tol=VALUE_TOLERANCE):
            raise ValueError("cash-flow amount must equal quantity * amount_per_share")
        return self


class DistributedSecurityTransformation(BaseModel):
    """Auditable quantity and basis state for one security received in an event."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    ticker: str
    quantity: float = Field(gt=0)
    cost_basis_status: CostBasisStatus

    _normalize_ticker = field_validator("ticker")(_ticker)


class CorporateActionTransformation(BaseModel):
    """Auditable holding/cash transformation from one reviewed complex event."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    transformation_id: str = Field(min_length=1)
    event_id: str = Field(min_length=1)
    ticker: str
    event_type: str = Field(min_length=1)
    record_date: date | None = None
    entitlement_date: date
    effective_date: date
    processed_at: datetime
    treatment_type: str = Field(min_length=1)
    treatment_version: str = Field(min_length=1)
    quantity_before: float = Field(ge=0)
    quantity_after: float = Field(ge=0)
    distributed_securities: tuple[DistributedSecurityTransformation, ...] = ()
    cash_received: float = Field(default=0, ge=0)
    notes: str = ""

    _normalize_ticker = field_validator("ticker")(_ticker)
    _validate_processed_at = field_validator("processed_at")(_aware)

    @model_validator(mode="after")
    def validate_distribution(self) -> "CorporateActionTransformation":
        tickers = [item.ticker for item in self.distributed_securities]
        if len(tickers) != len(set(tickers)):
            raise ValueError("distributed security transformations must be unique")
        return self


class BacktestResult(BaseModel):
    """Complete, auditable output of one deterministic historical run."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    run_id: str = Field(min_length=1)
    config: BacktestConfig
    allocations: list[TargetAllocation] = Field(default_factory=list)
    snapshots: list[PortfolioSnapshot] = Field(default_factory=list)
    orders: list[SimulatedOrder] = Field(default_factory=list)
    fills: list[SimulatedFill] = Field(default_factory=list)
    executions: list[OrderExecutionRecord] = Field(default_factory=list)
    cash_flows: list[CorporateActionCashFlow] = Field(default_factory=list)
    corporate_action_transformations: list[CorporateActionTransformation] = Field(
        default_factory=list,
    )
    realized_pnl: float = 0
    final_unrealized_pnl: float = 0
    pnl_incomplete_tickers: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class PerformanceMetrics(BaseModel):
    """NAV-based performance statistics for one ordered session range."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    start_date: date
    end_date: date
    initial_nav: float = Field(gt=0)
    final_nav: float = Field(gt=0)
    session_count: int = Field(ge=1)
    return_observation_count: int = Field(ge=0)
    cumulative_return: float
    cagr: float | None = None
    annualized_volatility: float | None = Field(default=None, ge=0)
    sharpe_ratio: float | None = None
    sortino_ratio: float | None = None
    max_drawdown: float = Field(le=0)
    drawdown_peak_date: date | None = None
    drawdown_trough_date: date | None = None
    drawdown_recovery_date: date | None = None


class ExecutionMetrics(BaseModel):
    """Order-level execution outcomes; rates use execution records as denominator."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    total_orders: int = Field(ge=0)
    total_fills: int = Field(ge=0)
    total_execution_records: int = Field(ge=0)
    filled_orders: int = Field(ge=0)
    partially_filled_orders: int = Field(ge=0)
    unfilled_orders: int = Field(ge=0)
    pending_orders: int = Field(ge=0)
    fill_rate: float | None = Field(default=None, ge=0, le=1)
    partial_fill_rate: float | None = Field(default=None, ge=0, le=1)
    unfilled_rate: float | None = Field(default=None, ge=0, le=1)


class CostMetrics(BaseModel):
    """Audited execution costs and fill-notional turnover."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    gross_traded_notional: float = Field(ge=0)
    total_commissions: float = Field(ge=0)
    total_slippage_cost: float = Field(ge=0)
    total_transaction_cost: float = Field(ge=0)
    cost_over_initial_nav: float = Field(ge=0)
    cost_over_traded_notional: float | None = Field(default=None, ge=0)
    total_turnover: float = Field(ge=0)
    average_daily_turnover: float = Field(ge=0)
    annualized_turnover: float = Field(ge=0)


class ExposureMetrics(BaseModel):
    """Session-average exposure, cash, and position-count statistics."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    average_gross_exposure: float = Field(ge=0)
    average_net_exposure: float = Field(ge=0)
    average_cash_weight: float = Field(ge=0, le=1)
    minimum_cash_weight: float = Field(ge=0, le=1)
    maximum_cash_weight: float = Field(ge=0, le=1)
    maximum_positions: int = Field(ge=0)
    average_positions: float = Field(ge=0)


class CorporateActionMetrics(BaseModel):
    """Cash distributions reported separately from trading P&L."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    dividend_cash: float = Field(ge=0)
    dividend_cash_flow_count: int = Field(ge=0)
    cash_in_lieu: float = Field(ge=0)
    cash_in_lieu_count: int = Field(ge=0)
    recapitalization_cash: float = Field(default=0, ge=0)
    recapitalization_cash_flow_count: int = Field(default=0, ge=0)
    reviewed_transformation_count: int = Field(default=0, ge=0)


class BenchmarkMetrics(BaseModel):
    """Economically simulated benchmark and direct portfolio comparison."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    ticker: str
    run_id: str = Field(min_length=1)
    performance: PerformanceMetrics
    costs: CostMetrics
    excess_cumulative_return: float
    excess_cagr: float | None = None
    tracking_difference: float

    _normalize_ticker = field_validator("ticker")(_ticker)


class BacktestMetrics(BaseModel):
    """Stable JSON-serializable Phase 2A.3 economic report."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    metrics_version: str = Field(min_length=1)
    run_id: str = Field(min_length=1)
    backtest_config: dict[str, Any]
    performance: PerformanceMetrics
    execution: ExecutionMetrics
    costs: CostMetrics
    exposure: ExposureMetrics
    corporate_actions: CorporateActionMetrics
    realized_pnl: float
    final_unrealized_pnl: float
    total_trading_pnl: float | None
    trading_pnl_complete: bool = True
    unknown_cost_basis_tickers: list[str] = Field(default_factory=list)
    benchmark: BenchmarkMetrics | None = None
    warnings: list[str] = Field(default_factory=list)
