"""Validate Phase 3D walk-forward artifacts and sealed-TEST invariants."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pandas as pd

from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.models.walkforward import (
    FREQUENCIES,
    MODEL_AGE_BUCKETS,
    SEALED_TEST_START,
    WALKFORWARD_START,
    model_age_bucket,
    select_operational_frequency,
)

ROOT = Path("data/reports/models/phase3d")
MODELS = {"rf-small", "ridge-100"}
EXPECTED_RETRAINS = {"monthly": 72, "quarterly": 24, "semiannual": 12, "annual": 6}
EXPECTED_TOTAL_FITS = 228
YEARS = {str(year) for year in range(2016, 2022)}


def main() -> int:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((ROOT / "phase3d_walkforward_summary.json").read_text(encoding="utf-8"))
    policy_metrics = json.loads((ROOT / "policy_metrics.json").read_text(encoding="utf-8"))
    age_metrics = json.loads((ROOT / "model_age_metrics.json").read_text(encoding="utf-8"))
    fits = pd.read_parquet(ROOT / "fits.parquet")
    predictions = pd.read_parquet(ROOT / "walkforward_predictions.parquet")
    preprocessing = pd.read_parquet(ROOT / "fit_preprocessing.parquet")
    summary_frame = pd.read_parquet(ROOT / "summary.parquet")
    if manifest.get("phase") != "3D-walk-forward-robustness" or manifest.get("scope") != "3D.1-3D.4":
        raise ValueError("incorrect Phase 3D manifest identity")
    if manifest.get("mode") != "robustness-selection" or manifest.get("test_used") is not False:
        raise ValueError("Phase 3D manifest violates sealed robustness-selection mode")
    if summary.get("test_used") is not False or age_metrics.get("test_used") is not False:
        raise ValueError("Phase 3D summaries must declare test_used=false")
    if set(policy_metrics) != MODELS or set(summary_frame["model_family"]) != MODELS:
        raise ValueError("Phase 3D must contain exactly two frozen models")
    if len(summary_frame) != 8 or summary.get("policy_count") != 8:
        raise ValueError("Phase 3D must contain exactly eight policy evaluations")
    if len(fits) != EXPECTED_TOTAL_FITS or summary.get("fit_count") != EXPECTED_TOTAL_FITS:
        raise ValueError("Phase 3D fit count differs from 228")
    if fits["test_used"].ne(False).any() or predictions["test_used"].ne(False).any():
        raise ValueError("fit or prediction artifacts violate test_used=false")
    prediction_dates = pd.to_datetime(predictions["decision_date"]).dt.date
    if prediction_dates.min() < date(2016, 1, 1) or prediction_dates.max() >= SEALED_TEST_START:
        raise ValueError("predictions escape the 2016-2021 pseudo-OOS period")
    if set(pd.to_datetime(predictions["decision_date"]).dt.year.unique()) != set(range(2016, 2022)):
        raise ValueError("predictions lack one or more walk-forward years")
    if predictions.duplicated(["model_family", "retraining_frequency", "ticker", "decision_date"]).any():
        raise ValueError("duplicate ticker/date within a policy")
    if not set(predictions["fit_id"]) <= set(fits["fit_id"]):
        raise ValueError("prediction references an unknown fit")
    if set(preprocessing["fit_id"]) != set(fits["fit_id"]):
        raise ValueError("fit preprocessing metadata is incomplete")
    if (pd.to_datetime(fits["max_train_target_end_date"]).dt.date >= pd.to_datetime(fits["prediction_start"]).dt.date).any():
        raise ValueError("dynamic purge invariant failed in fit metadata")
    if (pd.to_datetime(fits["effective_training_end"]).dt.date >= pd.to_datetime(fits["prediction_start"]).dt.date).any():
        raise ValueError("training decisions overlap prediction period")
    if fits["rows_after_purge"].le(0).any() or (fits["rows_before_purge"] < fits["rows_after_purge"]).any():
        raise ValueError("invalid dynamic purge row counts")
    if not (fits["purged_rows"] == fits["rows_before_purge"] - fits["rows_after_purge"]).all():
        raise ValueError("purged row arithmetic is inconsistent")
    calendar = XNYSTradingCalendar()
    for model in MODELS:
        if set(policy_metrics[model]) != set(FREQUENCIES):
            raise ValueError(f"{model} does not contain all four frequencies")
        for frequency in FREQUENCIES:
            policy_fits = fits.loc[
                fits["model_family"].eq(model) & fits["frequency"].eq(frequency)
            ].sort_values("prediction_start")
            if len(policy_fits) != EXPECTED_RETRAINS[frequency]:
                raise ValueError(f"unexpected retrain count for {model}/{frequency}")
            if not policy_fits["prediction_sessions"].equals(policy_fits["scheduled_sessions"]):
                raise ValueError(f"missing predicted sessions in {model}/{frequency}")
            starts = pd.to_datetime(policy_fits["prediction_start"]).dt.date.tolist()
            ends = pd.to_datetime(policy_fits["prediction_end"]).dt.date.tolist()
            if starts[0] < WALKFORWARD_START:
                raise ValueError("walk-forward schedule starts before 2016")
            for previous_end, current_start in zip(ends, starts[1:]):
                if calendar.next_session(previous_end) != current_start:
                    raise ValueError(f"gap or overlap in {model}/{frequency} schedule")
            policy_predictions = predictions.loc[
                predictions["model_family"].eq(model)
                & predictions["retraining_frequency"].eq(frequency)
            ]
            expected_dates = []
            for start, end in zip(starts, ends):
                current = start
                while current <= end:
                    expected_dates.append(current)
                    current = calendar.next_session(current)
            if sorted(policy_predictions["decision_date"].unique()) != expected_dates:
                raise ValueError(f"prediction dates have gaps in {model}/{frequency}")
            if not (
                pd.to_datetime(policy_predictions["decision_date"])
                .ge(pd.to_datetime(policy_predictions["prediction_period_start"]))
                & pd.to_datetime(policy_predictions["decision_date"])
                .le(pd.to_datetime(policy_predictions["prediction_period_end"]))
            ).all():
                raise ValueError(f"prediction row escapes its fit period in {model}/{frequency}")
            metrics = policy_metrics[model][frequency]
            if set(metrics.get("by_year", {})) != YEARS:
                raise ValueError(f"incomplete yearly metrics for {model}/{frequency}")
            for key in ("overall", "stability", "operational_cost", "model_age"):
                if key not in metrics:
                    raise ValueError(f"missing {key} metrics for {model}/{frequency}")
            if set(metrics["model_age"]) != set(MODEL_AGE_BUCKETS):
                raise ValueError(f"invalid model-age buckets for {model}/{frequency}")
    rf_expected = {
        "n_estimators": 300, "max_depth": 4, "min_samples_leaf": 100,
        "max_features": "sqrt", "bootstrap": True, "random_state": 42, "n_jobs": -1,
    }
    for row in fits.itertuples(index=False):
        parameters = json.loads(row.hyperparameters)
        if row.model_family == "rf-small" and parameters != rf_expected:
            raise ValueError("RF-Small config differs from frozen Phase 3C profile")
        if row.model_family == "ridge-100" and parameters != {"alpha": 100.0}:
            raise ValueError("Ridge config differs from frozen Phase 3B candidate")
    expected_bucket = predictions["sessions_since_fit"].astype(int).map(model_age_bucket)
    if not expected_bucket.equals(predictions["model_age_bucket"]):
        raise ValueError("model-age bucket assignment is inconsistent")
    for model in MODELS:
        reproduced = select_operational_frequency(model, policy_metrics[model])
        persisted = summary["selected_operational_frequency"][model]
        if reproduced.selected_frequency != persisted["selected_frequency"]:
            raise ValueError(f"selected frequency is not reproducible for {model}")
    if any("test" in path.name.lower() for path in ROOT.rglob("*") if path.is_file()):
        raise ValueError("TEST-named artifact found in Phase 3D output")
    print(json.dumps({
        "status": "passed", "models": 2, "policies": 8, "fits": len(fits),
        "prediction_rows": len(predictions), "prediction_date_min": str(prediction_dates.min()),
        "prediction_date_max": str(prediction_dates.max()), "test_used": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
