"""Stable target and out-of-sample prediction contracts."""
from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_system.features.targets import DEFAULT_HORIZON, SUPPORTED_HORIZONS


class TargetTask(str, Enum):
    REGRESSION = "regression"
    CLASSIFICATION = "classification"
    RANKING = "ranking"


class TargetSpec(BaseModel):
    """Validated mapping from economic task and horizon to stored label metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    task: TargetTask
    horizon: Literal[5, 10, 20] = DEFAULT_HORIZON

    @property
    def target_column(self) -> str:
        prefix = {
            TargetTask.REGRESSION: "target_return",
            TargetTask.CLASSIFICATION: "target_positive",
            TargetTask.RANKING: "target_rank",
        }[self.task]
        return f"{prefix}_{self.horizon}d"

    @property
    def eligibility_column(self) -> str:
        return f"target_{self.horizon}d_training_eligible"

    @property
    def target_end_date_column(self) -> str:
        return f"target_end_date_{self.horizon}d"

    @property
    def purge_horizon(self) -> int:
        return self.horizon


class OutOfSamplePrediction(BaseModel):
    """A model forecast only; deliberately contains no allocation or order fields."""

    model_config = ConfigDict(extra="forbid")

    ticker: str = Field(min_length=1)
    decision_date: date
    prediction: float
    task: TargetTask
    target_name: str = Field(min_length=1)
    horizon: Literal[5, 10, 20]
    model_id: str = Field(min_length=1)
    training_cutoff: date
    split: Literal["validation", "test", "walk_forward"]
    generated_at: datetime
    is_out_of_sample: Literal[True] = True

    @model_validator(mode="after")
    def validate_target_and_cutoff(self) -> "OutOfSamplePrediction":
        spec = TargetSpec(task=self.task, horizon=self.horizon)
        if self.target_name != spec.target_column:
            raise ValueError(f"target_name must be {spec.target_column!r} for task/horizon")
        if self.training_cutoff >= self.decision_date:
            raise ValueError("training_cutoff must be earlier than decision_date")
        if self.horizon not in SUPPORTED_HORIZONS:  # defensive if the Literal changes
            raise ValueError("unsupported horizon")
        if self.generated_at.tzinfo is None or self.generated_at.utcoffset() is None:
            raise ValueError("generated_at must be timezone-aware")
        return self
