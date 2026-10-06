"""Backtest-only contracts for historical orders, fills, and portfolio state."""
from __future__ import annotations

from datetime import datetime
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


class BacktestConfig(BaseModel):
    """Simulator-specific settings; global market timing stays in Settings."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    initial_cash: float = Field(gt=0)
    commission_bps: float = Field(default=0, ge=0)
    slippage_bps: float = Field(default=0, ge=0)
    allow_fractional_shares: bool = True
    benchmark_ticker: str = "SPY"

    _normalize_benchmark = field_validator("benchmark_ticker")(_ticker)


class BacktestPosition(BaseModel):
    """Long-only position in real units; market value is always derived."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    ticker: str
    quantity: float = Field(gt=0)
    average_cost: float = Field(gt=0)
    market_price: float = Field(gt=0)

    _normalize_ticker = field_validator("ticker")(_ticker)

    @computed_field
    @property
    def market_value(self) -> float:
        return self.quantity * self.market_price


class TargetAllocation(BaseModel):
    """Target weights produced upstream; this is not an executable order."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    generated_at: datetime
    weights: dict[str, float] = Field(default_factory=dict)
    cash_weight: float = Field(ge=0, le=1)

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
    ticker: str
    side: OrderSide
    quantity: float = Field(gt=0)
    submitted_at: datetime
    target_weight: float = Field(ge=0, le=1)
    reference_price: float = Field(gt=0)

    _normalize_ticker = field_validator("ticker")(_ticker)
    _validate_submitted_at = field_validator("submitted_at")(_aware)


class SimulatedFill(BaseModel):
    """A simulated execution priced from the raw next-session opening price."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
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

    _validate_as_of = field_validator("as_of")(_aware)

    @model_validator(mode="after")
    def validate_snapshot(self) -> "PortfolioSnapshot":
        tickers = [position.ticker for position in self.positions]
        if len(tickers) != len(set(tickers)):
            raise ValueError("snapshot contains duplicate positions")
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


class BacktestResult(BaseModel):
    """Result envelope for a future engine; no temporal loop is implemented here."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    config: BacktestConfig
    snapshots: list[PortfolioSnapshot] = Field(default_factory=list)
    orders: list[SimulatedOrder] = Field(default_factory=list)
    fills: list[SimulatedFill] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)

