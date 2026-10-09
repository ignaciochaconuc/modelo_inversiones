"""Execute Phase 3D.5 on existing label-safe data without opening TEST."""
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd
import sklearn

from investment_system.core.config import load_settings
from investment_system.core.reproducibility import git_metadata
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.models.feature_sets import (
    QUANTITATIVE_BASELINE_FEATURES,
    QUANTITATIVE_BASELINE_VERSION,
)
from investment_system.models.nonlinear_profiles import RANDOM_STATE, TREE_PROFILES
from investment_system.models.tree_preprocessing import TREE_PREPROCESSING_VERSION
from investment_system.models.walkforward import (
    ELIGIBILITY_COLUMN,
    RANK_COLUMN,
    SEALED_TEST_START,
    TARGET_COLUMN,
    TARGET_END_COLUMN,
    WALKFORWARD_END,
    WALKFORWARD_START,
    WALKFORWARD_PURGE_RULE_VERSION,
    build_walkforward_frame,
)
from investment_system.models.window_sensitivity import (
    MATERIAL_IMPROVEMENT_THRESHOLD,
    REAL_REPRO_TOLERANCE,
    WINDOW_IC_TOLERANCE,
    WINDOW_POLICIES,
    Phase3DWindowSensitivityRunner,
    interpret_window_results,
    select_training_window,
    training_sample_summary,
    window_deltas,
)

OUTPUT_ROOT = Path("data/reports/models/phase3d/window_sensitivity")
REFERENCE_SUMMARY = Path("data/reports/models/phase3d/phase3d_walkforward_summary.json")


def _years(files: list[Path], first: int, last: int) -> list[Path]:
    return [path for path in files if first <= int(path.parent.name.split("=")[1]) <= last]


def _read_features(files: list[Path]) -> pd.DataFrame:
    columns = [
        "ticker", "decision_date", "model_eligible", "feature_corporate_action_contaminated",
        *QUANTITATIVE_BASELINE_FEATURES,
    ]
    return pd.concat([pd.read_parquet(path, columns=columns) for path in files], ignore_index=True)


def _read_label_safe_targets(files: list[Path]) -> pd.DataFrame:
    columns = [
        "ticker", "decision_date", TARGET_COLUMN, RANK_COLUMN,
        TARGET_END_COLUMN, ELIGIBILITY_COLUMN,
    ]
    return pd.concat([
        pd.read_parquet(
            path, columns=columns, filters=[(TARGET_END_COLUMN, "<", SEALED_TEST_START)],
        ) for path in files
    ], ignore_index=True)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def _reference_ic() -> float:
    prior = json.loads(REFERENCE_SUMMARY.read_text(encoding="utf-8"))
    return float(
        prior["policy_results"]["rf-small"]["annual"]
        ["overall"]["ranking"]["rank_ic"]["mean"]
    )


def _summary_row(
    policy: str, metrics: dict[str, Any], sample: dict[str, Any],
    deltas: dict[str, dict[str, Any]], selected: str,
) -> dict[str, Any]:
    rank = metrics["overall"]["ranking"]["rank_ic"]
    top10 = metrics["overall"]["ranking"]["top10"]
    delta = deltas.get(policy, {
        "delta_mean_ic_vs_expanding": 0.0,
        "delta_icir_vs_expanding": 0.0,
        "delta_worst_year_ic_vs_expanding": 0.0,
        "delta_top10_uplift_vs_expanding": 0.0,
        "material_improvement_vs_expanding": False,
    })
    return {
        "window_policy": policy,
        "fits": metrics["operational_cost"]["number_of_retrains"],
        "mean_ic": rank["mean"],
        "median_ic": rank["median"],
        "icir": rank["icir"],
        "pct_positive_ic": rank["pct_positive"],
        **metrics["stability"],
        "top10_uplift": top10["average_top10_uplift"],
        "pct_dates_positive_uplift": top10["pct_dates_positive_uplift"],
        **sample,
        **delta,
        "selected": policy == selected,
        "test_used": False,
    }


def main() -> int:
    settings = load_settings()
    store = QuantitativeFeatureStore(
        settings.paths.features, settings.paths.features.parent / "targets",
    )
    feature_files = _years(sorted(store.features.glob("year=*/data.parquet")), 2010, 2021)
    target_files = _years(sorted(store.targets.glob("year=*/data.parquet")), 2010, 2021)
    if not feature_files or not target_files:
        raise ValueError("Phase 3D.5 requires existing 2010-2021 Feature and Target Stores")
    frame = build_walkforward_frame(
        _read_features(feature_files), _read_label_safe_targets(target_files),
    )
    effective_end = max(frame.loc[frame["decision_date"] >= WALKFORWARD_START, "decision_date"])
    runner = Phase3DWindowSensitivityRunner(OUTPUT_ROOT, XNYSTradingCalendar())
    all_predictions: list[pd.DataFrame] = []
    all_fits: list[pd.DataFrame] = []
    all_preprocessing: list[pd.DataFrame] = []
    all_metrics: dict[str, dict[str, Any]] = {}
    samples: dict[str, dict[str, Any]] = {}

    def progress(row: dict[str, Any]) -> None:
        print(json.dumps({
            "fit_id": row["fit_id"],
            "fit_seconds": round(row["fit_seconds"], 3),
            "rows_after_purge": row["rows_after_purge"],
            "test_used": False,
        }), flush=True)

    for policy in WINDOW_POLICIES:
        predictions, fits, preprocessing, metrics = runner.run_policy(
            frame, policy, progress=progress,
        )
        all_predictions.append(predictions)
        all_fits.append(fits)
        all_preprocessing.append(preprocessing)
        all_metrics[policy] = metrics
        samples[policy] = training_sample_summary(fits)
        print(json.dumps({
            "policy_complete": policy,
            "fits": len(fits),
            "mean_ic": metrics["overall"]["ranking"]["rank_ic"]["mean"],
            "test_used": False,
        }), flush=True)

    predictions = pd.concat(all_predictions, ignore_index=True)
    fits = pd.concat(all_fits, ignore_index=True)
    preprocessing = pd.concat(all_preprocessing, ignore_index=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(OUTPUT_ROOT / "predictions.parquet", index=False)
    fits.to_parquet(OUTPUT_ROOT / "fits.parquet", index=False)
    preprocessing.to_parquet(OUTPUT_ROOT / "fit_preprocessing.parquet", index=False)
    _write_json(OUTPUT_ROOT / "policy_metrics.json", all_metrics)

    reference_ic = _reference_ic()
    reproduced_ic = float(
        all_metrics["expanding"]["overall"]["ranking"]["rank_ic"]["mean"]
    )
    reproduction = {
        "reference_artifact": str(REFERENCE_SUMMARY),
        "reference_mean_ic": reference_ic,
        "reproduced_mean_ic": reproduced_ic,
        "absolute_difference": abs(reproduced_ic - reference_ic),
        "tolerance": REAL_REPRO_TOLERANCE,
        "passed": abs(reproduced_ic - reference_ic) <= REAL_REPRO_TOLERANCE,
    }
    if not reproduction["passed"]:
        _write_json(OUTPUT_ROOT / "reproduction_failure.json", {
            "phase": "3D.5", "expanding_reproduction_check": reproduction,
            "interpretation_performed": False, "test_used": False,
        })
        raise RuntimeError("expanding failed to reproduce Phase 3D; interpretation stopped")

    selection = select_training_window(all_metrics)
    deltas = window_deltas(all_metrics)
    interpretation = interpret_window_results(all_metrics, selection)
    summary_rows = [
        _summary_row(policy, all_metrics[policy], samples[policy], deltas, selection.selected_window)
        for policy in WINDOW_POLICIES
    ]
    summary_frame = pd.DataFrame(summary_rows)
    summary_frame.to_csv(OUTPUT_ROOT / "summary.csv", index=False)
    summary_frame.to_parquet(OUTPUT_ROOT / "summary.parquet", index=False)

    profile = next(item for item in TREE_PROFILES if item.profile_id == "rf-small")
    manifest = {
        "phase": "3D-training-window-sensitivity",
        "scope": "3D.5",
        "mode": "robustness-selection",
        "model": "RF-Small",
        "model_family": "rf-small",
        "task": "regression",
        "target": TARGET_COLUMN,
        "horizon": 20,
        "economic_use": "predicted return -> cross-sectional ranking",
        "feature_set_version": QUANTITATIVE_BASELINE_VERSION,
        "feature_count": len(QUANTITATIVE_BASELINE_FEATURES),
        "preprocessing_version": TREE_PREPROCESSING_VERSION,
        "retraining_frequency": "annual",
        "window_policies": list(WINDOW_POLICIES),
        "window_ic_tolerance": WINDOW_IC_TOLERANCE,
        "material_improvement_threshold": MATERIAL_IMPROVEMENT_THRESHOLD,
        "real_reproduction_tolerance": REAL_REPRO_TOLERANCE,
        "pseudo_oos_dates": [str(WALKFORWARD_START), str(WALKFORWARD_END)],
        "effective_label_safe_prediction_end": str(effective_end),
        "sealed_test_start": str(SEALED_TEST_START),
        "purge_rule": f"decision_date < prediction_start and {TARGET_END_COLUMN} < prediction_start",
        "purge_rule_version": WALKFORWARD_PURGE_RULE_VERSION,
        "hyperparameters": profile.parameters,
        "random_state": RANDOM_STATE,
        "feature_schema_version": settings.features.schema_version,
        "target_schema_version": settings.features.target_version,
        "sklearn_version": sklearn.__version__,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        **git_metadata(),
        "test_used": False,
    }
    summary = {
        **manifest,
        "fit_count": int(len(fits)),
        "prediction_rows": int(len(predictions)),
        "window_results": {
            policy: {"metrics": all_metrics[policy], "training_sample": samples[policy]}
            for policy in WINDOW_POLICIES
        },
        "deltas_vs_expanding": deltas,
        "raw_best_window": selection.raw_best_window,
        "selected_window": selection.selected_window,
        "selection": asdict(selection),
        "selection_rationale": selection.rationale,
        "expanding_reproduction_check": reproduction,
        "concept_drift_interpretation": interpretation,
        "test_used": False,
    }
    _write_json(OUTPUT_ROOT / "manifest.json", manifest)
    _write_json(OUTPUT_ROOT / "phase3d_window_summary.json", summary)
    print(json.dumps({
        "status": "passed",
        "fits": len(fits),
        "prediction_rows": len(predictions),
        "raw_best_window": selection.raw_best_window,
        "selected_window": selection.selected_window,
        "expanding_reproduction": reproduction,
        "test_used": False,
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
