"""Run the frozen Phase 3C selection experiment on real TRAIN/VALIDATION data."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd

from investment_system.core.config import load_settings
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.universe import load_universe
from investment_system.features.targets import TARGET_COLUMNS, TARGET_METADATA_COLUMNS
from investment_system.models.contracts import TargetSpec
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.phase3b import selection_dataset
from investment_system.models.phase3c import (
    Phase3CSelectionRunner,
    compact_result,
    compare_to_phase3b,
    select_candidate,
)
from investment_system.models.supervised import SupervisedDatasetBuilder

OUTPUT_ROOT = Path("data/reports/models/phase3c")
PHASE3B_ROOT = Path("data/reports/models/phase3b")
HORIZONS = (5, 10, 20)
FAMILIES = ("rf", "xgb", "lgbm")


def _read(files: list[Path], columns: list[str]) -> pd.DataFrame:
    return pd.concat([pd.read_parquet(path, columns=columns) for path in files], ignore_index=True)


def _actual_returns(partition: Any, targets: pd.DataFrame, horizon: int) -> pd.Series:
    column = f"target_return_{horizon}d"
    aligned = partition.metadata[["ticker", "decision_date"]].merge(
        targets[["ticker", "decision_date", column]],
        on=["ticker", "decision_date"], how="left", validate="one_to_one",
    )
    if aligned[column].isna().any():
        raise ValueError(f"ranking partition lacks valid {column}")
    return aligned[column].astype(float)


def _baseline_with_full_metrics(summary_item: dict[str, Any]) -> dict[str, Any]:
    """Read missing fields from persisted 3B metrics; never retrain the baseline."""
    item = dict(summary_item)
    metrics_path = PHASE3B_ROOT / item["experiment_id"] / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    overall = metrics["overall"]
    item["balanced_accuracy"] = overall.get("balanced_accuracy")
    item["top10_uplift"] = overall.get("top10", {}).get("average_top10_uplift")
    item["by_year"] = metrics["by_year"]
    return item


def main() -> int:
    settings = load_settings()
    universe = load_universe()
    store = QuantitativeFeatureStore(settings.paths.features, settings.paths.features.parent / "targets")
    feature_files = sorted(store.features.glob("year=*/data.parquet"))
    target_files = sorted(store.targets.glob("year=*/data.parquet"))
    if not feature_files or not target_files:
        raise ValueError("Phase 3C requires existing real Feature and v3 Target Stores")
    features = _read(feature_files, [
        "ticker", "decision_date", "model_eligible", "feature_corporate_action_contaminated",
        *QUANTITATIVE_BASELINE_FEATURES,
    ])
    targets = _read(target_files, ["ticker", "decision_date", *TARGET_COLUMNS, *TARGET_METADATA_COLUMNS])
    builder = SupervisedDatasetBuilder(
        XNYSTradingCalendar(), feature_schema_version=settings.features.schema_version,
        target_schema_version=settings.features.target_version, universe=universe.universe.name,
    )
    runner = Phase3CSelectionRunner(
        OUTPUT_ROOT, feature_schema_version=settings.features.schema_version,
        target_schema_version=settings.features.target_version, mode="selection",
    )
    family_winners: dict[str, dict[str, Any]] = {task: {} for task in ("regression", "classification", "ranking")}
    horizon_winners: dict[str, dict[str, Any]] = {task: {} for task in ("regression", "classification", "ranking")}

    for horizon in HORIZONS:
        regression_spec = TargetSpec(task="regression", horizon=horizon)
        regression_data = selection_dataset(builder.build(
            features, targets, regression_spec, feature_columns=QUANTITATIVE_BASELINE_FEATURES,
        ))
        regression = runner.run_models(regression_data, regression_spec, task="regression")

        classification_spec = TargetSpec(task="classification", horizon=horizon)
        classification_data = selection_dataset(builder.build(
            features, targets, classification_spec, feature_columns=QUANTITATIVE_BASELINE_FEATURES,
        ))
        classification = runner.run_models(classification_data, classification_spec, task="classification")

        ranking_spec = TargetSpec(task="ranking", horizon=horizon)
        ranking_data = selection_dataset(builder.build(
            features, targets, ranking_spec, feature_columns=QUANTITATIVE_BASELINE_FEATURES,
        ))
        actual_returns = _actual_returns(ranking_data.validation, targets, horizon)
        derived = runner.derive_ranking(ranking_data, ranking_spec, actual_returns, regression)
        direct = runner.run_models(
            ranking_data, ranking_spec, task="ranking", actual_returns=actual_returns,
        )

        by_task = {"regression": regression, "classification": classification, "ranking": [*derived, *direct]}
        selected_this_horizon = []
        for task, candidates in by_task.items():
            winners = []
            for family in FAMILIES:
                winner = select_candidate([item for item in candidates if item.family == family])
                family_winners[task][f"{family}_{horizon}d"] = winner
                winners.append(winner)
            overall = select_candidate(winners)
            horizon_winners[task][f"{horizon}d"] = overall
            selected_this_horizon.extend(winners)

        # Exactly 3 families x 3 tasks per horizon; all permutation data is VALIDATION only.
        for winner in selected_this_horizon:
            runner.persist_feature_importance(winner)
        retained_ids = {item.experiment_id for item in selected_this_horizon}
        for result in [*regression, *classification, *derived, *direct]:
            if result.experiment_id not in retained_ids:
                result.model = None
                result.preprocessor = None
                result.validation_x = None
                result.validation_y = None
                result.validation_metadata = None
        print(json.dumps({
            "horizon_complete": horizon, "fits": 27, "derived_evaluations": 9,
            "feature_importance_winners": 9, "test_used": False,
        }))

    family_values = [item for values in family_winners.values() for item in values.values()]
    horizon_values = [item for values in horizon_winners.values() for item in values.values()]
    summary_frame = runner.persist_summary(family_values, horizon_values)

    baseline_summary = json.loads((PHASE3B_ROOT / "phase3b_summary.json").read_text(encoding="utf-8"))
    baseline_sections = {
        "regression": baseline_summary["best_regression_model_by_horizon"],
        "classification": baseline_summary["best_classification_model_by_horizon"],
        "ranking": baseline_summary["best_ranking_approach_by_horizon"],
    }
    comparisons: dict[str, Any] = {}
    family_comparisons: dict[str, Any] = {}
    for task in ("regression", "classification", "ranking"):
        comparisons[task] = {}
        family_comparisons[task] = {}
        for horizon in HORIZONS:
            key = f"{horizon}d"
            winner = compact_result(horizon_winners[task][key])
            baseline = _baseline_with_full_metrics(baseline_sections[task][key])
            comparisons[task][key] = {
                "phase3b_experiment_id": baseline["experiment_id"],
                "phase3c_experiment_id": winner["experiment_id"],
                **compare_to_phase3b(task, winner, baseline),
            }
            for family in FAMILIES:
                family_key = f"{family}_{horizon}d"
                family_winner = compact_result(family_winners[task][family_key])
                family_comparisons[task][family_key] = {
                    "phase3b_experiment_id": baseline["experiment_id"],
                    "phase3c_experiment_id": family_winner["experiment_id"],
                    **compare_to_phase3b(task, family_winner, baseline),
                }

    global_manifest = runner.global_manifest()
    phase_summary = {
        **global_manifest, "fit_count": int(summary_frame["is_fit"].sum()),
        "experiment_count": int(len(summary_frame)), "derived_ranking_evaluations": 27,
        "best_by_family_task_horizon": {
            task: {key: compact_result(value) for key, value in values.items()}
            for task, values in family_winners.items()
        },
        "best_nonlinear_by_task_horizon": {
            task: {key: compact_result(value) for key, value in values.items()}
            for task, values in horizon_winners.items()
        },
        "phase3b_comparisons": comparisons,
        "phase3b_comparisons_by_family": family_comparisons,
        "phase3b_summary_reference": str(PHASE3B_ROOT / "phase3b_summary.json"),
        "feature_names": list(QUANTITATIVE_BASELINE_FEATURES), "test_used": False,
    }
    runner._write_json(OUTPUT_ROOT / "phase3c_summary.json", phase_summary)
    runner._write_json(OUTPUT_ROOT / "manifest.json", global_manifest)
    print(json.dumps({
        "status": "passed", "fits": int(summary_frame["is_fit"].sum()),
        "experiments": len(summary_frame), "feature_importance_artifacts": len(family_values),
        "output": str(OUTPUT_ROOT), "test_used": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
