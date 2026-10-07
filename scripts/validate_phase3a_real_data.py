"""Validate the real v3 Target Store and Phase 3A supervised split contracts."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from investment_system.core.config import load_settings
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.schemas.features import TARGET_COLUMNS
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.universe import load_universe
from investment_system.features.targets import (
    SUPPORTED_HORIZONS,
    TARGET_METADATA_COLUMNS,
    TARGET_SCHEMA_VERSION,
)
from investment_system.features.validation import validate_target_frame
from investment_system.models.contracts import TargetSpec
from investment_system.models.supervised import SupervisedDatasetBuilder

REPORT_PATH = Path("data/reports/phase3a1_target_validation.json")


def _future_session(calendar: XNYSTradingCalendar, origin: date, horizon: int) -> date:
    result = origin
    for _ in range(horizon):
        result = calendar.next_session(result)
    return result


def _load_columns(files: list[Path], columns: list[str]) -> pd.DataFrame:
    return pd.concat(
        [pd.read_parquet(path, columns=columns) for path in files], ignore_index=True
    )


def _ranking_validation(targets: pd.DataFrame, horizon: int, minimum_assets: int) -> dict[str, Any]:
    return_column = f"target_return_{horizon}d"
    rank_column = f"target_rank_{horizon}d"
    eligibility_column = f"target_{horizon}d_training_eligible"
    eligible = targets[eligibility_column].fillna(False) & targets[return_column].notna()
    eligible_returns = targets[return_column].where(eligible)
    counts = eligible_returns.groupby(targets["decision_date"]).transform("count")
    average_ranks = eligible_returns.groupby(targets["decision_date"]).rank(method="average")
    expected = ((average_ranks - 1) / (counts - 1)).where(counts >= minimum_assets)
    actual = targets[rank_column]
    if not np.allclose(
        actual.to_numpy(dtype=float), expected.to_numpy(dtype=float), equal_nan=True
    ):
        raise ValueError(f"{rank_column} does not match eligible average-rank semantics")
    values = actual.dropna()
    if not values.between(0, 1).all():
        raise ValueError(f"{rank_column} is outside [0, 1]")
    if (actual.notna() & ~eligible).any():
        raise ValueError(f"{rank_column} contains an ineligible observation")
    eligible_frame = targets.loc[eligible, ["decision_date", return_column]]
    tie_groups = int(
        (eligible_frame.groupby(["decision_date", return_column]).size() > 1).sum()
    )
    ranked_counts = targets[actual.notna()].groupby("decision_date")["ticker"].nunique()
    return {
        "valid_rows": int(actual.notna().sum()),
        "dates_with_ranking": int(actual.notna().groupby(targets["decision_date"]).any().sum()),
        "rank_min": float(values.min()) if not values.empty else None,
        "rank_max": float(values.max()) if not values.empty else None,
        "minimum_ranked_assets": int(ranked_counts.min()) if not ranked_counts.empty else 0,
        "eligible_tie_groups_checked": tie_groups,
        "average_rank_exact_match": True,
        "monotonic_with_return": True,
    }


def _corporate_action_validation(
    targets: pd.DataFrame, events: pd.DataFrame
) -> dict[str, Any]:
    excluded = events[events["training_exclusion"].fillna(False)].copy()
    event_dates = {
        ticker: list(pd.to_datetime(group["event_date"]).dt.date)
        for ticker, group in excluded.groupby("ticker")
    }
    result: dict[str, Any] = {"excluded_events": int(len(excluded)), "by_horizon": {}}
    decision_dates = pd.to_datetime(targets["decision_date"]).dt.date
    for horizon in SUPPORTED_HORIZONS:
        end_column = f"target_end_date_{horizon}d"
        contaminated_column = f"target_corporate_action_contaminated_{horizon}d"
        eligibility_column = f"target_{horizon}d_training_eligible"
        return_column = f"target_return_{horizon}d"
        end_dates = pd.to_datetime(targets[end_column]).dt.date
        expected = pd.Series(False, index=targets.index)
        for ticker, dates in event_dates.items():
            ticker_mask = targets["ticker"].eq(ticker)
            for event_date in dates:
                expected |= ticker_mask & decision_dates.lt(event_date) & end_dates.ge(event_date)
        actual = targets[contaminated_column].fillna(False).astype(bool)
        if not actual.equals(expected):
            raise ValueError(f"{contaminated_column} differs from excluded-event windows")
        expected_eligible = targets[return_column].notna() & ~expected
        if not targets[eligibility_column].fillna(False).astype(bool).equals(expected_eligible):
            raise ValueError(f"{eligibility_column} does not exclude contamination/missing labels")
        result["by_horizon"][f"{horizon}d"] = {
            "contaminated_rows": int(actual.sum()),
            "training_eligible_rows": int(expected_eligible.sum()),
        }
    counts = [
        result["by_horizon"][f"{horizon}d"]["contaminated_rows"]
        for horizon in SUPPORTED_HORIZONS
    ]
    if counts != sorted(counts):
        raise ValueError("corporate-action contamination does not expand with horizon")
    result["contamination_non_decreasing_by_horizon"] = True
    return result


def main() -> int:
    settings = load_settings()
    universe = load_universe()
    calendar = XNYSTradingCalendar()
    store = QuantitativeFeatureStore(
        settings.paths.features, settings.paths.features.parent / "targets"
    )
    target_files = sorted(store.targets.glob("year=*/data.parquet"))
    feature_files = sorted(store.features.glob("year=*/data.parquet"))
    if not target_files or not feature_files:
        raise ValueError("real feature and target stores are required")
    targets = _load_columns(target_files, ["ticker", "decision_date", *TARGET_COLUMNS, *TARGET_METADATA_COLUMNS])
    validate_target_frame(targets)
    expected_columns = {"ticker", "decision_date", *TARGET_COLUMNS, *TARGET_METADATA_COLUMNS}
    if set(targets.columns) != expected_columns:
        raise ValueError("Target Store columns differ from the v3 registry")
    feature_schema_columns = set(pd.read_parquet(feature_files[0]).columns)
    leakage = feature_schema_columns & (set(TARGET_COLUMNS) | set(TARGET_METADATA_COLUMNS))
    if leakage:
        raise ValueError(f"Feature Store contains target data: {sorted(leakage)}")
    if targets.duplicated(["ticker", "decision_date"]).any():
        raise ValueError("Target Store contains duplicate natural keys")
    if set(targets["ticker"]) != set(universe.tickers):
        raise ValueError("Target Store tickers differ from development_fixed")

    decision_dates = pd.to_datetime(targets["decision_date"]).dt.date
    unique_dates = sorted(set(decision_dates))
    end_date_validation: dict[str, Any] = {}
    expected_end: dict[int, pd.Series] = {}
    for horizon in SUPPORTED_HORIZONS:
        mapping = {day: _future_session(calendar, day, horizon) for day in unique_dates}
        expected = decision_dates.map(mapping)
        actual = pd.to_datetime(targets[f"target_end_date_{horizon}d"]).dt.date
        if not actual.equals(expected):
            raise ValueError(f"target_end_date_{horizon}d is not the exact future XNYS session")
        expected_end[horizon] = expected
        end_date_validation[f"{horizon}d"] = {
            "rows_checked": int(len(actual)), "exact_xnys_match": True
        }
    if not (
        (expected_end[5] < expected_end[10]).all()
        and (expected_end[10] < expected_end[20]).all()
    ):
        raise ValueError("target end dates are not strictly ordered")

    positive_validation: dict[str, Any] = {}
    coverage: dict[str, Any] = {}
    ranking: dict[str, Any] = {}
    for horizon in SUPPORTED_HORIZONS:
        return_column = f"target_return_{horizon}d"
        positive_column = f"target_positive_{horizon}d"
        eligibility_column = f"target_{horizon}d_training_eligible"
        contaminated_column = f"target_corporate_action_contaminated_{horizon}d"
        returns = targets[return_column]
        positives = targets[positive_column]
        expected_positive = (returns > 0).astype("Int64").mask(returns.isna(), pd.NA)
        if not positives.astype("Int64").equals(expected_positive):
            raise ValueError(f"{positive_column} is inconsistent with {return_column}")
        positive_validation[f"{horizon}d"] = {
            "rows_checked": int(len(targets)), "exact_match": True
        }
        coverage[f"{horizon}d"] = {
            "valid_targets": int(returns.notna().sum()),
            "training_eligible": int(targets[eligibility_column].fillna(False).sum()),
            "contaminated": int(targets[contaminated_column].fillna(False).sum()),
            "valid_rankings": int(targets[f"target_rank_{horizon}d"].notna().sum()),
            "missing_targets": int(returns.isna().sum()),
        }
        ranking[f"{horizon}d"] = _ranking_validation(
            targets, horizon, settings.features.minimum_rank_assets
        )
    valid_counts = [coverage[f"{horizon}d"]["valid_targets"] for horizon in SUPPORTED_HORIZONS]
    if not valid_counts[0] > valid_counts[1] > valid_counts[2]:
        raise ValueError("end-of-sample valid target counts do not decrease by horizon")

    events = MarketDataStore(settings.paths.raw, settings.paths.processed).read_corporate_action_events()
    corporate_actions = _corporate_action_validation(targets, events)

    feature_columns = [
        "ticker", "decision_date", "model_eligible",
        "feature_corporate_action_contaminated", "return_1d",
    ]
    features = _load_columns(feature_files, feature_columns)
    supervised_builder = SupervisedDatasetBuilder(
        calendar,
        feature_schema_version=settings.features.schema_version,
        target_schema_version=settings.features.target_version,
        universe=universe.universe.name,
    )
    smoke_specs = [
        TargetSpec(task="regression", horizon=5),
        TargetSpec(task="regression", horizon=10),
        TargetSpec(task="regression", horizon=20),
        TargetSpec(task="classification", horizon=10),
        TargetSpec(task="ranking", horizon=10),
    ]
    supervised: dict[str, Any] = {}
    for spec in smoke_specs:
        dataset = supervised_builder.build(
            features, targets, spec, feature_columns=["return_1d"]
        )
        counts = dataset.manifest["row_counts"]
        key = f"{spec.task.value}_{spec.horizon}d"
        supervised[key] = {
            "rows": counts["final"],
            "decision_dates": dataset.manifest["decision_date_counts"],
            "eligibility_removed": {
                split: counts["before_eligibility"][split] - counts["after_eligibility"][split]
                for split in ("train", "validation", "test")
            },
            "purging_removed": {
                split: counts["after_eligibility"][split] - counts["after_purging"][split]
                for split in ("train", "validation", "test")
            },
            "train_labels_before_validation": bool(
                dataset.train.metadata[spec.target_end_date_column].lt(date(2019, 1, 2)).all()
            ),
            "validation_labels_before_test": bool(
                dataset.validation.metadata[spec.target_end_date_column].lt(date(2022, 1, 3)).all()
            ),
            "test_all_target_eligible": bool(
                dataset.test.metadata[spec.eligibility_column].fillna(False).all()
            ),
        }
    regression_purges = {
        horizon: supervised[f"regression_{horizon}d"]["purging_removed"]
        for horizon in SUPPORTED_HORIZONS
    }
    if len({json.dumps(value, sort_keys=True) for value in regression_purges.values()}) < 2:
        raise ValueError("real-data purging does not vary by target horizon")

    manifest = json.loads((store.features / "manifest.json").read_text(encoding="utf-8"))
    full_report = json.loads(Path("data/reports/full_universe_build.json").read_text(encoding="utf-8"))
    reproducibility = full_report["reproducibility"]
    for document, name in ((manifest, "manifest"), (reproducibility, "full-universe report")):
        if document.get("target_version") != TARGET_SCHEMA_VERSION:
            raise ValueError(f"{name} target_version is not v3")
        if document.get("target_schema_version") != TARGET_SCHEMA_VERSION:
            raise ValueError(f"{name} target_schema_version is not v3")
        if document.get("target_columns") != list(TARGET_COLUMNS):
            raise ValueError(f"{name} target_columns differ from registry")
        if document.get("target_metadata_columns") != list(TARGET_METADATA_COLUMNS):
            raise ValueError(f"{name} target metadata differs from registry")

    report = {
        "phase": "3A.1-target-store-v3-real-data-validation",
        "status": "passed",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_schema_version": TARGET_SCHEMA_VERSION,
        "dataset": {
            "rows": int(len(targets)),
            "tickers": int(targets["ticker"].nunique()),
            "first_decision_date": min(decision_dates),
            "last_decision_date": max(decision_dates),
            "duplicates": 0,
            "feature_target_store_separation": True,
            "target_columns": list(TARGET_COLUMNS),
            "target_metadata_columns": list(TARGET_METADATA_COLUMNS),
        },
        "coverage": coverage,
        "target_end_dates": {
            **end_date_validation, "strictly_ordered": True,
        },
        "positive_targets": positive_validation,
        "ranking": ranking,
        "corporate_actions": corporate_actions,
        "end_of_sample": {
            "valid_targets_strictly_decrease_5d_10d_20d": True,
            "missing_targets_are_not_training_eligible": True,
        },
        "manifest": {
            "feature_manifest_generated_at": manifest["generated_at"],
            "full_universe_report_generated_at": reproducibility["generated_at"],
            "target_version": manifest["target_version"],
            "target_schema_version": manifest["target_schema_version"],
            "universe": manifest["universe_name"],
            "survivorship_bias_warning": manifest["survivorship_bias_warning"],
            "minimum_rank_assets": manifest["settings"]["minimum_rank_assets"],
        },
        "supervised_smoke_test": supervised,
        "purging_varies_by_horizon": True,
    }
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps(report, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
