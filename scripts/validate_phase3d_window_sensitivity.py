"""Validate Phase 3D.5 artifacts and sealed-TEST invariants."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pandas as pd

from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.tree_preprocessing import TREE_PREPROCESSING_VERSION
from investment_system.models.walkforward import SEALED_TEST_START, WALKFORWARD_START
from investment_system.models.window_sensitivity import (
    REAL_REPRO_TOLERANCE,
    WINDOW_POLICIES,
    nominal_window_start,
    select_training_window,
)

ROOT = Path("data/reports/models/phase3d/window_sensitivity")
REFERENCE = Path("data/reports/models/phase3d/phase3d_walkforward_summary.json")
YEARS = {str(year) for year in range(2016, 2022)}
EXPECTED_RF = {
    "n_estimators": 300,
    "max_depth": 4,
    "min_samples_leaf": 100,
    "max_features": "sqrt",
    "bootstrap": True,
    "random_state": 42,
    "n_jobs": -1,
}


def _check_schedule(fits: pd.DataFrame, predictions: pd.DataFrame, policy: str) -> None:
    calendar = XNYSTradingCalendar()
    policy_fits = fits.loc[fits["window_policy"].eq(policy)].sort_values("prediction_start")
    if len(policy_fits) != 6:
        raise ValueError(f"{policy} does not contain six annual fits")
    starts = pd.to_datetime(policy_fits["prediction_start"]).dt.date.tolist()
    ends = pd.to_datetime(policy_fits["prediction_end"]).dt.date.tolist()
    if [value.year for value in starts] != list(range(2016, 2022)):
        raise ValueError(f"{policy} annual activations do not cover 2016-2021")
    for previous_end, current_start in zip(ends, starts[1:]):
        if calendar.next_session(previous_end) != current_start:
            raise ValueError(f"gap or overlap in {policy} annual schedule")
    if not policy_fits["prediction_sessions"].equals(policy_fits["scheduled_sessions"]):
        raise ValueError(f"eligible predictions do not cover scheduled sessions for {policy}")
    policy_predictions = predictions.loc[predictions["window_policy"].eq(policy)]
    expected_dates: list[date] = []
    for start, end in zip(starts, ends):
        current = start
        while current <= end:
            expected_dates.append(current)
            current = calendar.next_session(current)
    if sorted(policy_predictions["decision_date"].unique()) != expected_dates:
        raise ValueError(f"prediction dates have gaps for {policy}")


def main() -> int:
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((ROOT / "phase3d_window_summary.json").read_text(encoding="utf-8"))
    metrics = json.loads((ROOT / "policy_metrics.json").read_text(encoding="utf-8"))
    fits = pd.read_parquet(ROOT / "fits.parquet")
    predictions = pd.read_parquet(ROOT / "predictions.parquet")
    preprocessing = pd.read_parquet(ROOT / "fit_preprocessing.parquet")
    summary_frame = pd.read_parquet(ROOT / "summary.parquet")
    if manifest.get("scope") != "3D.5" or manifest.get("mode") != "robustness-selection":
        raise ValueError("incorrect Phase 3D.5 manifest identity")
    if manifest.get("model_family") != "rf-small" or manifest.get("retraining_frequency") != "annual":
        raise ValueError("Phase 3D.5 must contain only annual RF-Small")
    if manifest.get("hyperparameters") != EXPECTED_RF:
        raise ValueError("manifest RF-Small config is not frozen")
    if manifest.get("feature_count") != 52 or len(QUANTITATIVE_BASELINE_FEATURES) != 52:
        raise ValueError("Phase 3D.5 feature set must contain exactly 52 features")
    if manifest.get("preprocessing_version") != TREE_PREPROCESSING_VERSION:
        raise ValueError("incorrect tree preprocessing version")
    if set(manifest.get("window_policies", [])) != set(WINDOW_POLICIES):
        raise ValueError("manifest does not contain exactly three window policies")
    if len(fits) != 18 or summary.get("fit_count") != 18:
        raise ValueError("Phase 3D.5 must contain exactly 18 fits")
    if set(fits["window_policy"]) != set(WINDOW_POLICIES) or set(metrics) != set(WINDOW_POLICIES):
        raise ValueError("artifacts do not contain exactly the three window policies")
    if fits["model_family"].ne("rf-small").any() or fits["frequency"].ne("annual").any():
        raise ValueError("unexpected model or frequency in fits")
    if any(frame["test_used"].ne(False).any() for frame in (fits, predictions, summary_frame)):
        raise ValueError("tabular artifacts violate test_used=false")
    if manifest.get("test_used") is not False or summary.get("test_used") is not False:
        raise ValueError("JSON artifacts violate test_used=false")
    dates = pd.to_datetime(predictions["decision_date"]).dt.date
    if dates.min() < WALKFORWARD_START or dates.max() >= SEALED_TEST_START:
        raise ValueError("predictions escape label-safe pseudo-OOS")
    if set(pd.to_datetime(predictions["decision_date"]).dt.year.unique()) != set(range(2016, 2022)):
        raise ValueError("predictions lack one or more years")
    if predictions.duplicated(["window_policy", "ticker", "decision_date"]).any():
        raise ValueError("duplicate ticker/date inside a window policy")
    if not set(predictions["fit_id"]) <= set(fits["fit_id"]):
        raise ValueError("prediction references unknown fit")
    if (pd.to_datetime(fits["max_train_target_end_date"]) >= pd.to_datetime(fits["prediction_start"])).any():
        raise ValueError("strict target-end purge failed")
    if (pd.to_datetime(fits["effective_training_end"]) >= pd.to_datetime(fits["prediction_start"])).any():
        raise ValueError("training decisions overlap prediction")
    if not (fits["purged_rows"] == fits["rows_before_purge"] - fits["rows_after_purge"]).all():
        raise ValueError("purge row arithmetic is inconsistent")
    if fits["rows_after_purge"].le(0).any():
        raise ValueError("empty training fit")
    for row in fits.itertuples(index=False):
        prediction_start = pd.Timestamp(row.prediction_start).date()
        expected_start = nominal_window_start(prediction_start, row.window_policy)
        if pd.Timestamp(row.nominal_window_start).date() != expected_start:
            raise ValueError(f"incorrect nominal start for {row.fit_id}")
        if pd.Timestamp(row.effective_training_start).date() < expected_start:
            raise ValueError(f"effective start precedes policy boundary for {row.fit_id}")
        if json.loads(row.hyperparameters) != EXPECTED_RF:
            raise ValueError(f"RF parameters changed in {row.fit_id}")
        if row.preprocessing_version != TREE_PREPROCESSING_VERSION or row.feature_count != 52:
            raise ValueError(f"preprocessing contract changed in {row.fit_id}")
    counts = preprocessing.groupby("fit_id").size()
    if set(counts.index) != set(fits["fit_id"]) or counts.ne(52).any():
        raise ValueError("each fit must persist all 52 preprocessing rows")
    if preprocessing["fit_partition"].ne("train").any():
        raise ValueError("preprocessing was not fit on TRAIN")
    if set(preprocessing["original_feature"]) != set(QUANTITATIVE_BASELINE_FEATURES):
        raise ValueError("preprocessing contains a non-feature or misses a feature")
    for policy in WINDOW_POLICIES:
        _check_schedule(fits, predictions, policy)
        if set(metrics[policy].get("by_year", {})) != YEARS:
            raise ValueError(f"incomplete annual metrics for {policy}")
    reproduced_selection = select_training_window(metrics)
    if reproduced_selection.selected_window != summary.get("selected_window"):
        raise ValueError("selected window is not reproducible")
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    reference_ic = float(
        reference["policy_results"]["rf-small"]["annual"]
        ["overall"]["ranking"]["rank_ic"]["mean"]
    )
    expanded_ic = float(metrics["expanding"]["overall"]["ranking"]["rank_ic"]["mean"])
    if abs(expanded_ic - reference_ic) > REAL_REPRO_TOLERANCE:
        raise ValueError("expanding does not reproduce the prior Phase 3D artifact")
    check = summary.get("expanding_reproduction_check", {})
    if check.get("passed") is not True or abs(check.get("absolute_difference", 1.0)) > REAL_REPRO_TOLERANCE:
        raise ValueError("persisted reproduction check is inconsistent")
    if len(summary_frame) != 3 or summary_frame["selected"].sum() != 1:
        raise ValueError("summary must contain three policies and one selection")
    if set(summary_frame["window_policy"]) != set(WINDOW_POLICIES):
        raise ValueError("summary policies are incomplete")
    if any("test" in path.name.lower() for path in ROOT.rglob("*") if path.is_file()):
        raise ValueError("TEST-named artifact found in Phase 3D.5 output")
    print(json.dumps({
        "status": "passed",
        "policies": len(WINDOW_POLICIES),
        "fits": len(fits),
        "prediction_rows": len(predictions),
        "prediction_date_min": str(dates.min()),
        "prediction_date_max": str(dates.max()),
        "selected_window": reproduced_selection.selected_window,
        "expanding_reproduction_absolute_difference": abs(expanded_ic - reference_ic),
        "test_used": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
