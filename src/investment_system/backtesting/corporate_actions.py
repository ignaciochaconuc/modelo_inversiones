"""Typed, reviewed economic treatments for otherwise unsupported corporate actions."""
from __future__ import annotations

from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from investment_system.core.config import load_yaml


class EntitlementTiming(StrEnum):
    """When the portfolio quantity entitled to a treatment is observed."""

    PRE_OPEN = "pre_open"
    POST_CLOSE = "post_close"


class CostBasisPolicy(StrEnum):
    """Supported accounting policy for a security received without a purchase fill."""

    UNALLOCATED = "unallocated"


class FractionalDistributionPolicy(StrEnum):
    """Conservative behavior when official fractional-settlement proceeds are absent."""

    BLOCK_WITHOUT_ACTUAL_SETTLEMENT_PRICE = "block_without_actual_settlement_price"


class ProviderActionType(StrEnum):
    """Normalized provider records economically consumed by a reviewed treatment."""

    DIVIDEND = "dividend"
    SPLIT = "split"


class ReviewedTreatmentBase(BaseModel):
    """Fields shared by every versioned, event-specific economic treatment."""

    model_config = ConfigDict(frozen=True, extra="forbid", allow_inf_nan=False)
    event_id: str = Field(min_length=1)
    ticker: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    record_date: date | None = None
    effective_date: date
    processing_date: date
    entitlement_date: date
    entitlement_timing: EntitlementTiming
    treatment_type: str
    treatment_version: str = Field(min_length=1)
    provider_action_types_consumed: tuple[ProviderActionType, ...]
    evidence: tuple[str, ...] = Field(min_length=1)
    review_notes: str = Field(min_length=1)

    @field_validator("ticker")
    @classmethod
    def normalize_ticker(cls, value: str) -> str:
        normalized = value.strip().upper()
        if not normalized:
            raise ValueError("ticker must not be empty")
        return normalized

    @model_validator(mode="after")
    def validate_dates(self) -> "ReviewedTreatmentBase":
        if self.record_date is not None and self.record_date > self.entitlement_date:
            raise ValueError("record_date must be <= entitlement_date")
        if self.entitlement_date > self.effective_date:
            raise ValueError("entitlement_date must be <= effective_date")
        if self.effective_date > self.processing_date:
            raise ValueError("effective_date must be <= processing_date")
        if len(self.provider_action_types_consumed) != len(
            set(self.provider_action_types_consumed)
        ):
            raise ValueError("provider_action_types_consumed must be unique")
        return self


class SpinOffDistributionTreatment(ReviewedTreatmentBase):
    """Distribute shares of a new security while leaving the parent position intact."""

    treatment_type: Literal["spin_off_distribution"]
    distributed_ticker: str
    shares_per_parent_share: float = Field(gt=0)
    cost_basis_policy: CostBasisPolicy = CostBasisPolicy.UNALLOCATED
    fractional_policy: FractionalDistributionPolicy

    _normalize_distributed_ticker = field_validator("distributed_ticker")(
        ReviewedTreatmentBase.normalize_ticker.__func__
    )

    @model_validator(mode="after")
    def validate_consumed_actions(self) -> "SpinOffDistributionTreatment":
        if self.record_date is None:
            raise ValueError("spin-off treatment requires its legal record_date")
        if ProviderActionType.DIVIDEND not in self.provider_action_types_consumed:
            raise ValueError("spin-off treatment must consume the provider dividend record")
        return self


class RecapitalizationCashAndSplitTreatment(ReviewedTreatmentBase):
    """Apply a reverse/forward split and separate return-of-capital cash payment."""

    treatment_type: Literal["recapitalization_cash_and_split"]
    split_factor: float = Field(gt=0)
    cash_per_pre_split_share: float = Field(gt=0)

    @model_validator(mode="after")
    def validate_consumed_actions(self) -> "RecapitalizationCashAndSplitTreatment":
        required = {ProviderActionType.DIVIDEND, ProviderActionType.SPLIT}
        if not required.issubset(self.provider_action_types_consumed):
            raise ValueError("recapitalization treatment must consume split and dividend records")
        return self


ReviewedTreatment = Annotated[
    SpinOffDistributionTreatment | RecapitalizationCashAndSplitTreatment,
    Field(discriminator="treatment_type"),
]


class ReviewedCorporateActionTreatments(BaseModel):
    """Validated registry keyed by the persisted complex-event identifier."""

    model_config = ConfigDict(frozen=True, extra="forbid")
    schema_version: str = Field(min_length=1)
    treatments: tuple[ReviewedTreatment, ...] = ()

    @model_validator(mode="after")
    def unique_events(self) -> "ReviewedCorporateActionTreatments":
        event_ids = [item.event_id for item in self.treatments]
        if len(event_ids) != len(set(event_ids)):
            raise ValueError("reviewed treatment event_id values must be unique")
        return self

    def get(self, event_id: str) -> ReviewedTreatment | None:
        return next((item for item in self.treatments if item.event_id == event_id), None)

    def treatments_entitled_on(
        self, day: date, timing: EntitlementTiming,
    ) -> tuple[ReviewedTreatment, ...]:
        return tuple(
            item for item in self.treatments
            if item.entitlement_date == day and item.entitlement_timing == timing
        )

    def auxiliary_tickers(self) -> set[str]:
        return {
            item.distributed_ticker
            for item in self.treatments
            if isinstance(item, SpinOffDistributionTreatment)
        }


def load_reviewed_corporate_action_treatments(
    path: str | Path = "config/reviewed_corporate_action_treatments.yaml",
) -> ReviewedCorporateActionTreatments:
    """Load the versioned registry; malformed or free-form rules fail validation."""
    return ReviewedCorporateActionTreatments.model_validate(load_yaml(path))
