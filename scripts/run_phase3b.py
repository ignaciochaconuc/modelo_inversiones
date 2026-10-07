"""Run Phase 3B model selection on TRAIN and VALIDATION; never evaluate TEST."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from investment_system.core.config import load_settings
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.universe import load_universe
from investment_system.features.targets import TARGET_COLUMNS, TARGET_METADATA_COLUMNS
from investment_system.models.contracts import TargetSpec
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.phase3b import Phase3BSelectionRunner, selection_dataset
from investment_system.models.supervised import SupervisedDatasetBuilder

OUTPUT_ROOT = Path("data/reports/models/phase3b")


def _read(files: list[Path], columns: list[str]) -> pd.DataFrame:
    return pd.concat(
        [pd.read_parquet(path, columns=columns) for path in files], ignore_index=True
    )


def _actual_returns(partition, targets: pd.DataFrame, horizon: int) -> pd.Series:
    column = f"target_return_{horizon}d"
    aligned = partition.metadata[["ticker", "decision_date"]].merge(
        targets[["ticker", "decision_date", column]],
        on=["ticker", "decision_date"], how="left", validate="one_to_one",
    )
    if aligned[column].isna().any():
        raise ValueError(f"ranking partition lacks valid {column}")
    return aligned[column].astype(float)


def main() -> int:
    settings = load_settings()
    universe = load_universe()
    store = QuantitativeFeatureStore(
        settings.paths.features, settings.paths.features.parent / "targets"
    )
    feature_files = sorted(store.features.glob("year=*/data.parquet"))
    target_files = sorted(store.targets.glob("year=*/data.parquet"))
    if not feature_files or not target_files:
        raise ValueError("Phase 3B requires the real Feature and v3 Target Stores")
    feature_columns = [
        "ticker", "decision_date", "model_eligible",
        "feature_corporate_action_contaminated", *QUANTITATIVE_BASELINE_FEATURES,
    ]
    features = _read(feature_files, feature_columns)
    targets = _read(
        target_files, ["ticker", "decision_date", *TARGET_COLUMNS, *TARGET_METADATA_COLUMNS]
    )
    dataset_builder = SupervisedDatasetBuilder(
        XNYSTradingCalendar(),
        feature_schema_version=settings.features.schema_version,
        target_schema_version=settings.features.target_version,
        universe=universe.universe.name,
    )
    runner = Phase3BSelectionRunner(
        OUTPUT_ROOT,
        feature_schema_version=settings.features.schema_version,
        target_schema_version=settings.features.target_version,
        mode="selection",
    )

    regression: dict[int, dict] = {}
    classification: dict[int, dict] = {}
    ranking: dict[int, dict] = {}
    for horizon in (5, 10, 20):
        spec = TargetSpec(task="regression", horizon=horizon)
        supervised = dataset_builder.build(
            features, targets, spec, feature_columns=QUANTITATIVE_BASELINE_FEATURES
        )
        regression[horizon] = runner.run_regression(selection_dataset(supervised), spec)

    for horizon in (5, 10, 20):
        spec = TargetSpec(task="classification", horizon=horizon)
        supervised = dataset_builder.build(
            features, targets, spec, feature_columns=QUANTITATIVE_BASELINE_FEATURES
        )
        classification[horizon] = runner.run_classification(selection_dataset(supervised), spec)

    for horizon in (5, 10, 20):
        spec = TargetSpec(task="ranking", horizon=horizon)
        supervised = dataset_builder.build(
            features, targets, spec, feature_columns=QUANTITATIVE_BASELINE_FEATURES
        )
        selection = selection_dataset(supervised)
        ranking[horizon] = runner.run_ranking(
            selection, spec,
            _actual_returns(selection.train, targets, horizon),
            _actual_returns(selection.validation, targets, horizon),
            regression[horizon],
        )

    selected_ids = {
        *(regression[horizon]["best_ridge"].experiment_id for horizon in (5, 10, 20)),
        *(classification[horizon]["best_logistic"].experiment_id for horizon in (5, 10, 20)),
        *(ranking[horizon]["best_approach"].experiment_id for horizon in (5, 10, 20)),
    }
    summary_frame = runner.persist_experiments(selected_ids)

    def compact(result) -> dict:
        metrics = result.metrics["overall"]
        daily = metrics.get("daily_spearman", metrics.get("rank_ic", {}))
        return {
            "experiment_id": result.experiment_id,
            "model_family": result.model_family,
            "hyperparameter": result.hyperparameter,
            "mean_ic": daily.get("mean"),
            "icir": daily.get("icir"),
            "pct_positive_ic": daily.get("pct_positive"),
            "rmse": metrics.get("pooled", {}).get("rmse"),
            "roc_auc": metrics.get("roc_auc"),
            "log_loss": metrics.get("log_loss"),
            "top10_uplift": metrics.get("top10", {}).get("average_top10_uplift"),
            "by_year": result.metrics["by_year"],
        }

    phase_summary = {
        **runner.global_manifest(),
        "experiments": int(len(summary_frame)),
        "best_regression_model_by_horizon": {
            f"{horizon}d": compact(regression[horizon]["best_ridge"])
            for horizon in (5, 10, 20)
        },
        "best_classification_model_by_horizon": {
            f"{horizon}d": compact(classification[horizon]["best_logistic"])
            for horizon in (5, 10, 20)
        },
        "best_ranking_approach_by_horizon": {
            f"{horizon}d": compact(ranking[horizon]["best_approach"])
            for horizon in (5, 10, 20)
        },
        "naive_baselines": {
            f"regression_{horizon}d": [compact(item) for item in regression[horizon]["naive"]]
            for horizon in (5, 10, 20)
        } | {
            f"classification_{horizon}d": compact(classification[horizon]["prior"])
            for horizon in (5, 10, 20)
        },
        "momentum_20d_comparison": {
            f"{horizon}d": compact(ranking[horizon]["momentum"])
            for horizon in (5, 10, 20)
        },
        "feature_names": list(QUANTITATIVE_BASELINE_FEATURES),
        "test_used": False,
    }
    runner._write_json(OUTPUT_ROOT / "phase3b_summary.json", phase_summary)
    runner._write_json(OUTPUT_ROOT / "manifest.json", runner.global_manifest())
    print(json.dumps({
        "status": "passed", "experiments": len(summary_frame),
        "output": str(OUTPUT_ROOT), "test_used": False,
        "selected": sorted(selected_ids),
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
