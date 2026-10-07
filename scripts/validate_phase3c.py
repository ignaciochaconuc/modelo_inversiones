"""Validate Phase 3C counts, sealed TEST, metrics, versions, and 3B references."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path("data/reports/models/phase3c")
PHASE3B_ROOT = Path("data/reports/models/phase3b")
EXPECTED_FITS = 81
EXPECTED_EXPERIMENTS = 108
EXPECTED_IMPORTANCE = 27
YEARS = {"2019", "2020", "2021"}


def main() -> int:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    summary_json = json.loads((ROOT / "phase3c_summary.json").read_text(encoding="utf-8"))
    parquet = pd.read_parquet(ROOT / "summary.parquet")
    csv = pd.read_csv(ROOT / "summary.csv")
    if manifest.get("test_used") is not False or summary_json.get("test_used") is not False:
        raise ValueError("global Phase 3C artifacts must declare test_used=false")
    for dependency in ("sklearn_version", "xgboost_version", "lightgbm_version"):
        if not manifest.get(dependency) or not summary_json.get(dependency):
            raise ValueError(f"missing executed dependency version: {dependency}")
    if len(parquet) != EXPECTED_EXPERIMENTS or len(csv) != EXPECTED_EXPERIMENTS:
        raise ValueError("Phase 3C must persist exactly 108 evaluated experiments")
    if int(parquet["is_fit"].sum()) != EXPECTED_FITS:
        raise ValueError("Phase 3C must persist exactly 81 fitted experiments")
    if parquet["test_used"].ne(False).any():
        raise ValueError("summary violates sealed-test mode")
    if set(parquet["experiment_id"]) != set(csv["experiment_id"]):
        raise ValueError("CSV and parquet summaries disagree")
    directories = [path for path in ROOT.iterdir() if path.is_dir()]
    if len(directories) != EXPECTED_EXPERIMENTS:
        raise ValueError("experiment directory count differs from expected count")
    importance_count = 0
    for directory in directories:
        lower_names = [item.name.lower() for item in directory.iterdir()]
        if any("test" in name for name in lower_names):
            raise ValueError(f"TEST-named artifact found in {directory.name}")
        item_manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        predictions = pd.read_parquet(directory / "validation_predictions.parquet")
        if item_manifest.get("mode") != "selection" or item_manifest.get("test_used") is not False:
            raise ValueError(f"{directory.name} is not sealed-test selection output")
        if not item_manifest.get("sklearn_version") or not item_manifest.get("xgboost_version") or not item_manifest.get("lightgbm_version"):
            raise ValueError(f"{directory.name} lacks dependency versions")
        dates = pd.to_datetime(predictions["decision_date"])
        if dates.min().date().isoformat() < "2019-01-02" or dates.max().date().isoformat() > "2021-12-31":
            raise ValueError(f"{directory.name} predictions escape VALIDATION")
        if set(dates.dt.year.unique()) - {2019, 2020, 2021}:
            raise ValueError(f"{directory.name} has non-validation years")
        if predictions.duplicated(["ticker", "decision_date"]).any():
            raise ValueError(f"{directory.name} has duplicate ticker/date predictions")
        if len(predictions) != item_manifest["validation_rows"]:
            raise ValueError(f"{directory.name} prediction count differs from manifest")
        if set(metrics.get("by_year", {})) != YEARS:
            raise ValueError(f"{directory.name} lacks complete by-year metrics")
        if not metrics.get("stability"):
            raise ValueError(f"{directory.name} lacks explicit stability diagnostics")
        importance = directory / "feature_importance.parquet"
        if importance.exists():
            importance_count += 1
            importance_frame = pd.read_parquet(importance)
            required = {"feature", "native_importance", "permutation_importance_mean", "permutation_importance_std", "permutation_metric"}
            if not required <= set(importance_frame):
                raise ValueError(f"{directory.name} feature importance schema is incomplete")
            if item_manifest.get("feature_importance_validation_only") is not True:
                raise ValueError(f"{directory.name} does not attest validation-only importance")
    if importance_count != EXPECTED_IMPORTANCE:
        raise ValueError(f"expected {EXPECTED_IMPORTANCE} winner feature-importance artifacts, got {importance_count}")
    if summary_json.get("fit_count") != EXPECTED_FITS or summary_json.get("experiment_count") != EXPECTED_EXPERIMENTS:
        raise ValueError("global summary counts are inconsistent")
    for task, horizons in summary_json.get("phase3b_comparisons", {}).items():
        if set(horizons) != {"5d", "10d", "20d"}:
            raise ValueError(f"incomplete Phase 3B comparison for {task}")
        for comparison in horizons.values():
            baseline_id = comparison.get("phase3b_experiment_id")
            if not baseline_id or not (PHASE3B_ROOT / baseline_id / "metrics.json").exists():
                raise ValueError(f"invalid persisted Phase 3B reference: {baseline_id}")
    family_comparisons = summary_json.get("phase3b_comparisons_by_family", {})
    expected_family_keys = {
        f"{family}_{horizon}d"
        for family in ("rf", "xgb", "lgbm") for horizon in (5, 10, 20)
    }
    for task in ("regression", "classification", "ranking"):
        if set(family_comparisons.get(task, {})) != expected_family_keys:
            raise ValueError(f"incomplete family-level Phase 3B comparisons for {task}")
    print(json.dumps({
        "status": "passed", "fits": EXPECTED_FITS, "experiments": EXPECTED_EXPERIMENTS,
        "feature_importance_artifacts": importance_count, "validation_years": sorted(YEARS),
        "test_used": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
