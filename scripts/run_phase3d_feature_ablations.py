"""Execute Phase 3D.6 feature-family ablations without opening TEST."""
from __future__ import annotations

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
from investment_system.models.feature_ablations import (
    ABLATION_MATERIAL_THRESHOLD,
    ABLATION_NEUTRAL_TOLERANCE,
    ABLATION_POLICIES,
    EXPECTED_FEATURE_COUNTS,
    FEATURE_FAMILIES,
    REAL_REPRO_TOLERANCE,
    Phase3DFeatureAblationRunner,
    classify_ablation,
    diagnostic_flags,
    policy_deltas,
    removed_family,
    validate_family_contract,
)
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

OUTPUT_ROOT = Path("data/reports/models/phase3d/feature_ablations")
REFERENCE_SUMMARY = Path(
    "data/reports/models/phase3d/window_sensitivity/phase3d_window_summary.json"
)
REPRO_METRICS = ("mean_ic", "icir", "worst_year_ic", "top10_uplift")


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


def _metric_vector(metrics: dict[str, Any]) -> dict[str, float]:
    rank = metrics["overall"]["ranking"]["rank_ic"]
    return {
        "mean_ic": float(rank["mean"]),
        "icir": float(rank["icir"]),
        "worst_year_ic": float(metrics["stability"]["worst_year_ic"]),
        "top10_uplift": float(
            metrics["overall"]["ranking"]["top10"]["average_top10_uplift"]
        ),
    }


def _reference_metrics() -> dict[str, float]:
    reference = json.loads(REFERENCE_SUMMARY.read_text(encoding="utf-8"))
    return _metric_vector(reference["window_results"]["expanding"]["metrics"])


def _reproduction_check(full_metrics: dict[str, Any]) -> dict[str, Any]:
    reference = _reference_metrics()
    reproduced = _metric_vector(full_metrics)
    differences = {name: abs(reproduced[name] - reference[name]) for name in REPRO_METRICS}
    return {
        "reference_artifact": str(REFERENCE_SUMMARY),
        "reference": reference,
        "reproduced": reproduced,
        "absolute_differences": differences,
        "tolerance": REAL_REPRO_TOLERANCE,
        "passed": all(value <= REAL_REPRO_TOLERANCE for value in differences.values()),
    }


def _summary_row(
    policy: str, metrics: dict[str, Any], all_metrics: dict[str, dict[str, Any]],
    fits: pd.DataFrame,
) -> dict[str, Any]:
    rank = metrics["overall"]["ranking"]["rank_ic"]
    top10 = metrics["overall"]["ranking"]["top10"]
    delta = policy_deltas(policy, all_metrics)
    if policy == "full":
        classification = "reference"
        flags = {"strong_contributor": False, "harmful_candidate": False}
    else:
        classification = classify_ablation(delta["delta_mean_ic_vs_full"])
        flags = diagnostic_flags(
            delta_mean_ic=delta["delta_mean_ic_vs_full"],
            delta_worst_year_ic=delta["delta_worst_year_ic_vs_full"],
            delta_icir=delta["delta_icir_vs_full"],
            delta_top10_uplift=delta["delta_top10_uplift_vs_full"],
        )
    return {
        "ablation_policy": policy,
        "removed_family": removed_family(policy),
        "requested_feature_count": EXPECTED_FEATURE_COUNTS[policy],
        "mean_effective_feature_count": float(fits["feature_count_effective"].mean()),
        "fits": int(len(fits)),
        "mean_ic": rank["mean"],
        "median_ic": rank["median"],
        "icir": rank["icir"],
        "pct_positive_ic": rank["pct_positive"],
        **metrics["stability"],
        "top10_uplift": top10["average_top10_uplift"],
        "pct_dates_positive_uplift": top10["pct_dates_positive_uplift"],
        **delta,
        "classification": classification,
        **flags,
        "total_fit_seconds": metrics["operational_cost"]["total_fit_seconds"],
        "mean_fit_seconds": metrics["operational_cost"]["mean_fit_seconds"],
        "median_fit_seconds": metrics["operational_cost"]["median_fit_seconds"],
        "test_used": False,
    }


def main() -> int:
    validate_family_contract()
    settings = load_settings()
    store = QuantitativeFeatureStore(
        settings.paths.features, settings.paths.features.parent / "targets",
    )
    feature_files = _years(sorted(store.features.glob("year=*/data.parquet")), 2010, 2021)
    target_files = _years(sorted(store.targets.glob("year=*/data.parquet")), 2010, 2021)
    if not feature_files or not target_files:
        raise ValueError("Phase 3D.6 requires existing 2010-2021 Feature and Target Stores")
    frame = build_walkforward_frame(
        _read_features(feature_files), _read_label_safe_targets(target_files),
    )
    effective_end = max(frame.loc[frame["decision_date"] >= WALKFORWARD_START, "decision_date"])
    runner = Phase3DFeatureAblationRunner(OUTPUT_ROOT, XNYSTradingCalendar())
    all_predictions: list[pd.DataFrame] = []
    all_fits: list[pd.DataFrame] = []
    all_preprocessing: list[pd.DataFrame] = []
    all_metrics: dict[str, dict[str, Any]] = {}
    fits_by_policy: dict[str, pd.DataFrame] = {}

    def progress(row: dict[str, Any]) -> None:
        print(json.dumps({
            "fit_id": row["fit_id"],
            "fit_seconds": round(row["fit_seconds"], 3),
            "feature_count_effective": row["feature_count_effective"],
            "test_used": False,
        }), flush=True)

    for index, policy in enumerate(ABLATION_POLICIES):
        predictions, fits, preprocessing, metrics = runner.run_policy(
            frame, policy, progress=progress,
        )
        all_predictions.append(predictions)
        all_fits.append(fits)
        all_preprocessing.append(preprocessing)
        all_metrics[policy] = metrics
        fits_by_policy[policy] = fits
        print(json.dumps({
            "policy_complete": policy,
            "policy_number": index + 1,
            "fits": len(fits),
            "mean_ic": metrics["overall"]["ranking"]["rank_ic"]["mean"],
            "test_used": False,
        }), flush=True)
        if policy == "full":
            reproduction = _reproduction_check(metrics)
            if not reproduction["passed"]:
                OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
                predictions.to_parquet(OUTPUT_ROOT / "predictions.partial.parquet", index=False)
                fits.to_parquet(OUTPUT_ROOT / "fits.partial.parquet", index=False)
                _write_json(OUTPUT_ROOT / "reproduction_failure.json", {
                    "phase": "3D.6", "full_reproduction_check": reproduction,
                    "interpretation_performed": False, "test_used": False,
                })
                raise RuntimeError("full failed to reproduce Phase 3D.5; interpretation stopped")

    predictions = pd.concat(all_predictions, ignore_index=True)
    fits = pd.concat(all_fits, ignore_index=True)
    preprocessing = pd.concat(all_preprocessing, ignore_index=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(OUTPUT_ROOT / "predictions.parquet", index=False)
    fits.to_parquet(OUTPUT_ROOT / "fits.parquet", index=False)
    preprocessing.to_parquet(OUTPUT_ROOT / "preprocessing.parquet", index=False)
    _write_json(OUTPUT_ROOT / "policy_metrics.json", all_metrics)

    rows = [
        _summary_row(policy, all_metrics[policy], all_metrics, fits_by_policy[policy])
        for policy in ABLATION_POLICIES
    ]
    rows.sort(key=lambda row: (row["delta_mean_ic_vs_full"], row["ablation_policy"]))
    summary_frame = pd.DataFrame(rows)
    summary_frame.to_csv(OUTPUT_ROOT / "summary.csv", index=False)
    summary_frame.to_parquet(OUTPUT_ROOT / "summary.parquet", index=False)
    ablation_rows = [row for row in rows if row["ablation_policy"] != "full"]
    strong = [row["removed_family"] for row in ablation_rows if row["strong_contributor"]]
    neutral = [
        row["removed_family"] for row in ablation_rows
        if row["classification"] == "neutral_or_redundant"
    ]
    potentially_harmful = [
        row["removed_family"] for row in ablation_rows
        if row["classification"] == "potentially_harmful"
    ]
    harmful_candidates = [
        row["removed_family"] for row in ablation_rows if row["harmful_candidate"]
    ]
    reproduction = _reproduction_check(all_metrics["full"])
    profile = next(item for item in TREE_PROFILES if item.profile_id == "rf-small")
    manifest = {
        "phase": "3D-feature-family-ablations",
        "scope": "3D.6",
        "mode": "diagnostic-robustness",
        "model": "RF-Small",
        "model_family": "rf-small",
        "task": "regression",
        "target": TARGET_COLUMN,
        "horizon": 20,
        "economic_use": "predicted return -> cross-sectional ranking",
        "retraining_frequency": "annual",
        "window_policy": "expanding",
        "training_start": "2010-01-04",
        "feature_set_version": QUANTITATIVE_BASELINE_VERSION,
        "full_feature_count": len(QUANTITATIVE_BASELINE_FEATURES),
        "feature_families": {name: list(values) for name, values in FEATURE_FAMILIES.items()},
        "ablation_policies": list(ABLATION_POLICIES),
        "expected_feature_counts": EXPECTED_FEATURE_COUNTS,
        "ablation_neutral_tolerance": ABLATION_NEUTRAL_TOLERANCE,
        "ablation_material_threshold": ABLATION_MATERIAL_THRESHOLD,
        "harmful_candidate_stability_rules": {
            "delta_mean_ic_min": 0.005,
            "delta_worst_year_ic_min": -0.003,
            "delta_icir_min": -0.02,
            "delta_top10_uplift_min": -0.001,
        },
        "pseudo_oos_dates": [str(WALKFORWARD_START), str(WALKFORWARD_END)],
        "effective_label_safe_prediction_end": str(effective_end),
        "sealed_test_start": str(SEALED_TEST_START),
        "purge_rule": f"decision_date < prediction_start and {TARGET_END_COLUMN} < prediction_start",
        "purge_rule_version": WALKFORWARD_PURGE_RULE_VERSION,
        "preprocessing_version": TREE_PREPROCESSING_VERSION,
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
        "policy_count": len(ABLATION_POLICIES),
        "fit_count": int(len(fits)),
        "prediction_rows": int(len(predictions)),
        "full_reference": rows[next(i for i, row in enumerate(rows) if row["ablation_policy"] == "full")],
        "ablation_results": {
            row["removed_family"]: row for row in ablation_rows
        },
        "sorted_feature_family_contribution_table": ablation_rows,
        "strongest_contributors": strong,
        "neutral_or_redundant_families": neutral,
        "potentially_harmful_families": potentially_harmful,
        "harmful_candidates": harmful_candidates,
        "full_reproduction_check": reproduction,
        "confirmation_subset_warranted": bool(harmful_candidates),
        "official_feature_set_changed": False,
        "adaptive_second_round_run": False,
        "test_used": False,
    }
    _write_json(OUTPUT_ROOT / "manifest.json", manifest)
    _write_json(OUTPUT_ROOT / "phase3d_feature_ablation_summary.json", summary)
    print(json.dumps({
        "status": "passed",
        "policies": len(ABLATION_POLICIES),
        "fits": len(fits),
        "prediction_rows": len(predictions),
        "strong_contributors": strong,
        "harmful_candidates": harmful_candidates,
        "confirmation_subset_warranted": bool(harmful_candidates),
        "full_reproduction": reproduction,
        "test_used": False,
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
