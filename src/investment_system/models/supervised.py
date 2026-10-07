"""Leakage-resistant supervised datasets and temporal fixed holdout splitting."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any, Sequence

import pandas as pd

from investment_system.core.reproducibility import git_metadata
from investment_system.data.calendar import TradingCalendar
from investment_system.data.schemas.features import CATEGORICAL_FEATURE_COLUMNS, FEATURE_COLUMNS, TARGET_COLUMNS
from investment_system.features.targets import TARGET_METADATA_COLUMNS, TARGET_SCHEMA_VERSION
from investment_system.models.contracts import TargetSpec, TargetTask

MODEL_FEATURE_COLUMNS = (*FEATURE_COLUMNS, *CATEGORICAL_FEATURE_COLUMNS)
PURGE_RULE_VERSION = "target-end-date-strict-v1"
SPLIT_MANIFEST_VERSION = "supervised-dataset-v1"


@dataclass(frozen=True)
class TemporalSplitSpec:
    """Inclusive decision-date ranges for a fixed holdout experiment.

    A positive embargo removes the first N XNYS sessions from validation and
    test. It does not replace label purging in the preceding split.
    """

    train_start: date = date(2010, 1, 4)
    train_end: date = date(2018, 12, 31)
    validation_start: date = date(2019, 1, 2)
    validation_end: date = date(2021, 12, 31)
    test_start: date = date(2022, 1, 3)
    test_end: date | None = None
    embargo_sessions: int = 0
    split_type: str = "fixed_holdout"

    def __post_init__(self) -> None:
        if self.split_type != "fixed_holdout":
            raise ValueError("only fixed_holdout is implemented in Phase 3A")
        if self.embargo_sessions < 0:
            raise ValueError("embargo_sessions must be non-negative")
        if not (
            self.train_start <= self.train_end < self.validation_start
            <= self.validation_end < self.test_start
        ):
            raise ValueError("temporal split ranges must be ordered and non-overlapping")
        if self.test_end is not None and self.test_end < self.test_start:
            raise ValueError("test_end must be on or after test_start")


OFFICIAL_FIXED_HOLDOUT = TemporalSplitSpec()


@dataclass(frozen=True)
class SupervisedPartition:
    X: pd.DataFrame
    y: pd.Series
    metadata: pd.DataFrame


@dataclass(frozen=True)
class SupervisedDataset:
    train: SupervisedPartition
    validation: SupervisedPartition
    test: SupervisedPartition
    manifest: dict[str, Any]

    def write_manifest(self, path: str | Path) -> Path:
        """Persist reconstruction metadata without an experiment platform."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(
            json.dumps(self.manifest, indent=2, default=str), encoding="utf-8"
        )
        return destination


def _assert_unique(frame: pd.DataFrame, name: str) -> None:
    keys = ["ticker", "decision_date"]
    missing = [column for column in keys if column not in frame]
    if missing:
        raise ValueError(f"{name} is missing key columns: {missing}")
    if frame.duplicated(keys).any():
        raise ValueError(f"duplicate ticker + decision_date in {name} dataset")


def _boolean_mask(values: pd.Series) -> pd.Series:
    """Normalize nullable/object boolean metadata without implicit downcasting."""
    return values.astype("boolean").fillna(False).astype(bool)


def _embargoed_sessions(start: date, count: int, calendar: TradingCalendar) -> set[date]:
    if count == 0:
        return set()
    session = start if calendar.is_session(start) else calendar.next_session(start)
    result: set[date] = set()
    for _ in range(count):
        result.add(session)
        session = calendar.next_session(session)
    return result


class SupervisedDatasetBuilder:
    """Join separate stores one-to-one, select X by allowlist, and split by date."""

    def __init__(
        self,
        calendar: TradingCalendar,
        *,
        feature_schema_version: str | None = None,
        target_schema_version: str = TARGET_SCHEMA_VERSION,
        universe: str = "development_fixed",
    ) -> None:
        self.calendar = calendar
        self.feature_schema_version = feature_schema_version
        self.target_schema_version = target_schema_version
        self.universe = universe

    def build(
        self,
        features: pd.DataFrame,
        targets: pd.DataFrame,
        target_spec: TargetSpec,
        split_spec: TemporalSplitSpec = OFFICIAL_FIXED_HOLDOUT,
        *,
        feature_columns: Sequence[str] | None = None,
    ) -> SupervisedDataset:
        _assert_unique(features, "feature")
        _assert_unique(targets, "target")
        selected = tuple(feature_columns) if feature_columns is not None else tuple(
            column for column in MODEL_FEATURE_COLUMNS if column in features.columns
        )
        unknown = sorted(set(selected) - set(MODEL_FEATURE_COLUMNS))
        if unknown:
            raise ValueError(f"columns are not registered model features: {unknown}")
        missing_features = sorted(set(selected) - set(features.columns))
        if missing_features:
            raise ValueError(f"selected feature columns are missing: {missing_features}")
        leaked = sorted((set(TARGET_COLUMNS) | set(TARGET_METADATA_COLUMNS)) & set(selected))
        if leaked:
            raise ValueError(f"target columns or metadata cannot enter X: {leaked}")
        required_feature_metadata = {"model_eligible", "feature_corporate_action_contaminated"}
        missing = sorted(required_feature_metadata - set(features.columns))
        if missing:
            raise ValueError(f"feature dataset is missing eligibility metadata: {missing}")
        required_targets = {
            target_spec.target_column,
            target_spec.eligibility_column,
            target_spec.target_end_date_column,
        }
        missing = sorted(required_targets - set(targets.columns))
        if missing:
            raise ValueError(f"target dataset is missing required columns: {missing}")

        feature_input = features[[
            "ticker", "decision_date", "model_eligible",
            "feature_corporate_action_contaminated", *selected,
        ]].copy()
        target_input = targets[["ticker", "decision_date", *sorted(required_targets)]].copy()
        joined = feature_input.merge(
            target_input, on=["ticker", "decision_date"], how="inner", validate="one_to_one"
        )
        joined["decision_date"] = pd.to_datetime(joined["decision_date"]).dt.date
        joined[target_spec.target_end_date_column] = pd.to_datetime(
            joined[target_spec.target_end_date_column], errors="coerce"
        ).dt.date
        joined["training_eligible"] = (
            _boolean_mask(joined["model_eligible"])
            & ~_boolean_mask(joined["feature_corporate_action_contaminated"])
            & _boolean_mask(joined[target_spec.eligibility_column])
            & joined[target_spec.target_column].notna()
        )
        if target_spec.task is TargetTask.RANKING:
            joined["training_eligible"] &= joined[target_spec.target_column].notna()

        masks = {
            "train": joined["decision_date"].between(split_spec.train_start, split_spec.train_end),
            "validation": joined["decision_date"].between(
                split_spec.validation_start, split_spec.validation_end
            ),
            "test": joined["decision_date"] >= split_spec.test_start,
        }
        if split_spec.test_end is not None:
            masks["test"] &= joined["decision_date"] <= split_spec.test_end

        pre_eligibility = {name: int(mask.sum()) for name, mask in masks.items()}
        eligible_masks = {name: mask & joined["training_eligible"] for name, mask in masks.items()}
        after_eligibility = {name: int(mask.sum()) for name, mask in eligible_masks.items()}

        end_dates = joined[target_spec.target_end_date_column]
        purged_masks = {
            "train": eligible_masks["train"] & (end_dates < split_spec.validation_start),
            "validation": eligible_masks["validation"] & (end_dates < split_spec.test_start),
            "test": eligible_masks["test"],
        }
        after_purge = {name: int(mask.sum()) for name, mask in purged_masks.items()}

        embargoed = {
            "validation": _embargoed_sessions(
                split_spec.validation_start, split_spec.embargo_sessions, self.calendar
            ),
            "test": _embargoed_sessions(split_spec.test_start, split_spec.embargo_sessions, self.calendar),
        }
        final_masks = {
            "train": purged_masks["train"],
            "validation": purged_masks["validation"] & ~joined["decision_date"].isin(embargoed["validation"]),
            "test": purged_masks["test"] & ~joined["decision_date"].isin(embargoed["test"]),
        }

        metadata_columns = [
            "ticker", "decision_date", "training_eligible",
            target_spec.eligibility_column, target_spec.target_end_date_column,
        ]

        def partition(mask: pd.Series) -> SupervisedPartition:
            rows = joined.loc[mask].sort_values(["decision_date", "ticker"])
            return SupervisedPartition(
                X=rows.loc[:, selected].reset_index(drop=True),
                y=rows[target_spec.target_column].reset_index(drop=True),
                metadata=rows.loc[:, metadata_columns].reset_index(drop=True),
            )

        manifest = {
            "manifest_schema_version": SPLIT_MANIFEST_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **git_metadata(),
            "target_spec": target_spec.model_dump(mode="json"),
            "target_name": target_spec.target_column,
            "task": target_spec.task.value,
            "horizon": target_spec.horizon,
            "split_type": split_spec.split_type,
            "dates": {
                "train": [str(split_spec.train_start), str(split_spec.train_end)],
                "validation": [str(split_spec.validation_start), str(split_spec.validation_end)],
                "test": [str(split_spec.test_start), str(split_spec.test_end) if split_spec.test_end else "latest"],
            },
            "embargo_sessions": split_spec.embargo_sessions,
            "embargo_semantics": "exclude first N XNYS sessions of validation and test",
            "purge_rule": "target_end_date < next_split_start",
            "purge_rule_version": PURGE_RULE_VERSION,
            "feature_schema_version": self.feature_schema_version,
            "target_schema_version": self.target_schema_version,
            "universe": self.universe,
            "feature_columns": list(selected),
            "row_counts": {
                "joined": int(len(joined)),
                "before_eligibility": pre_eligibility,
                "after_eligibility": after_eligibility,
                "after_purging": after_purge,
                "final": {name: int(mask.sum()) for name, mask in final_masks.items()},
            },
            "decision_date_counts": {
                name: int(joined.loc[mask, "decision_date"].nunique()) for name, mask in final_masks.items()
            },
        }
        return SupervisedDataset(
            train=partition(final_masks["train"]),
            validation=partition(final_masks["validation"]),
            test=partition(final_masks["test"]),
            manifest=manifest,
        )
