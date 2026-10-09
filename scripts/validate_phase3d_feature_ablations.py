"""Validate Phase 3D.6 artifacts and diagnostic invariants."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path

import pandas as pd

from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.models.feature_ablations import (
    ABLATION_POLICIES,
    EXPECTED_FEATURE_COUNTS,
    FEATURE_FAMILIES,
    REAL_REPRO_TOLERANCE,
    classify_ablation,
    diagnostic_flags,
    policy_deltas,
    validate_family_contract,
)
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.tree_preprocessing import TREE_PREPROCESSING_VERSION
from investment_system.models.walkforward import SEALED_TEST_START, WALKFORWARD_START

ROOT = Path("data/reports/models/phase3d/feature_ablations")
REFERENCE = Path("data/reports/models/phase3d/window_sensitivity/phase3d_window_summary.json")
YEARS = {str(year) for year in range(2016, 2022)}
EXPECTED_RF = {
    "n_estimators": 300, "max_depth": 4, "min_samples_leaf": 100,
    "max_features": "sqrt", "bootstrap": True, "random_state": 42, "n_jobs": -1,
}


def _metric_vector(metrics: dict) -> dict[str, float]:
    rank = metrics["overall"]["ranking"]["rank_ic"]
    return {
        "mean_ic": float(rank["mean"]),
        "icir": float(rank["icir"]),
        "worst_year_ic": float(metrics["stability"]["worst_year_ic"]),
        "top10_uplift": float(
            metrics["overall"]["ranking"]["top10"]["average_top10_uplift"]
        ),
    }


def _check_schedule(fits: pd.DataFrame, predictions: pd.DataFrame, policy: str) -> None:
    calendar = XNYSTradingCalendar()
    policy_fits = fits.loc[fits["ablation_policy"].eq(policy)].sort_values("prediction_start")
    if len(policy_fits) != 6:
        raise ValueError(f"{policy} does not contain six annual fits")
    starts = pd.to_datetime(policy_fits["prediction_start"]).dt.date.tolist()
    ends = pd.to_datetime(policy_fits["prediction_end"]).dt.date.tolist()
    if [value.year for value in starts] != list(range(2016, 2022)):
        raise ValueError(f"{policy} annual activations do not cover 2016-2021")
    for previous_end, current_start in zip(ends, starts[1:]):
        if calendar.next_session(previous_end) != current_start:
            raise ValueError(f"gap or overlap in {policy} schedule")
    if not policy_fits["prediction_sessions"].equals(policy_fits["scheduled_sessions"]):
        raise ValueError(f"missing scheduled sessions in {policy}")
    expected_dates: list[date] = []
    for start, end in zip(starts, ends):
        current = start
        while current <= end:
            expected_dates.append(current)
            current = calendar.next_session(current)
    actual_dates = sorted(
        predictions.loc[predictions["ablation_policy"].eq(policy), "decision_date"].unique()
    )
    if actual_dates != expected_dates:
        raise ValueError(f"prediction schedule is incomplete for {policy}")


def main() -> int:
    validate_family_contract()
    manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads(
        (ROOT / "phase3d_feature_ablation_summary.json").read_text(encoding="utf-8")
    )
    metrics = json.loads((ROOT / "policy_metrics.json").read_text(encoding="utf-8"))
    fits = pd.read_parquet(ROOT / "fits.parquet")
    preprocessing = pd.read_parquet(ROOT / "preprocessing.parquet")
    predictions = pd.read_parquet(ROOT / "predictions.parquet")
    summary_frame = pd.read_parquet(ROOT / "summary.parquet")
    if manifest.get("phase") != "3D-feature-family-ablations" or manifest.get("scope") != "3D.6":
        raise ValueError("incorrect Phase 3D.6 identity")
    if manifest.get("mode") != "diagnostic-robustness":
        raise ValueError("incorrect Phase 3D.6 mode")
    if manifest.get("model_family") != "rf-small" or manifest.get("task") != "regression":
        raise ValueError("only RF-Small regression is allowed")
    if manifest.get("retraining_frequency") != "annual" or manifest.get("window_policy") != "expanding":
        raise ValueError("frequency/window dimensions are not frozen")
    if manifest.get("target") != "target_return_20d" or manifest.get("horizon") != 20:
        raise ValueError("target dimension is not frozen")
    if manifest.get("hyperparameters") != EXPECTED_RF:
        raise ValueError("RF-Small configuration changed")
    if manifest.get("preprocessing_version") != TREE_PREPROCESSING_VERSION:
        raise ValueError("tree preprocessing version changed")
    persisted_families = {
        name: tuple(values) for name, values in manifest.get("feature_families", {}).items()
    }
    if persisted_families != FEATURE_FAMILIES:
        raise ValueError("persisted family taxonomy differs from code")
    if manifest.get("full_feature_count") != 52 or len(QUANTITATIVE_BASELINE_FEATURES) != 52:
        raise ValueError("official feature set no longer contains 52 features")
    if set(feature for values in persisted_families.values() for feature in values) != set(
        QUANTITATIVE_BASELINE_FEATURES
    ):
        raise ValueError("family union differs from official feature set")
    if tuple(manifest.get("ablation_policies", [])) != ABLATION_POLICIES:
        raise ValueError("policy list differs from the frozen eleven policies")
    if manifest.get("expected_feature_counts") != EXPECTED_FEATURE_COUNTS:
        raise ValueError("persisted feature counts are incorrect")
    if set(metrics) != set(ABLATION_POLICIES) or set(summary_frame["ablation_policy"]) != set(ABLATION_POLICIES):
        raise ValueError("policy artifacts are incomplete")
    if len(summary_frame) != 11 or summary.get("policy_count") != 11:
        raise ValueError("Phase 3D.6 must contain eleven policies")
    if len(fits) != 66 or summary.get("fit_count") != 66:
        raise ValueError("Phase 3D.6 must contain 66 fits")
    if fits["model_family"].ne("rf-small").any() or fits["frequency"].ne("annual").any():
        raise ValueError("unexpected model or frequency in fits")
    if fits["window_policy"].ne("expanding").any():
        raise ValueError("unexpected training window in fits")
    if any(frame["test_used"].ne(False).any() for frame in (fits, predictions, summary_frame)):
        raise ValueError("tabular artifacts violate test_used=false")
    if manifest.get("test_used") is not False or summary.get("test_used") is not False:
        raise ValueError("JSON artifacts violate test_used=false")
    dates = pd.to_datetime(predictions["decision_date"]).dt.date
    if dates.min() < WALKFORWARD_START or dates.max() >= SEALED_TEST_START:
        raise ValueError("predictions escape label-safe pseudo-OOS")
    if set(pd.to_datetime(predictions["decision_date"]).dt.year.unique()) != set(range(2016, 2022)):
        raise ValueError("prediction years are incomplete")
    if predictions.duplicated(["ablation_policy", "ticker", "decision_date"]).any():
        raise ValueError("duplicate ticker/date within an ablation policy")
    if (pd.to_datetime(fits["max_train_target_end_date"]) >= pd.to_datetime(fits["prediction_start"])).any():
        raise ValueError("strict target-end purge failed")
    if (pd.to_datetime(fits["effective_training_end"]) >= pd.to_datetime(fits["prediction_start"])).any():
        raise ValueError("training decisions overlap prediction")
    if not (fits["purged_rows"] == fits["rows_before_purge"] - fits["rows_after_purge"]).all():
        raise ValueError("purge row arithmetic is inconsistent")
    for row in fits.itertuples(index=False):
        if row.feature_count_requested != EXPECTED_FEATURE_COUNTS[row.ablation_policy]:
            raise ValueError(f"requested count differs for {row.fit_id}")
        excluded = json.loads(row.excluded_zero_variance_features)
        if row.feature_count_effective != row.feature_count_requested - len(excluded):
            raise ValueError(f"effective feature count differs for {row.fit_id}")
        if json.loads(row.hyperparameters) != EXPECTED_RF:
            raise ValueError(f"RF parameters changed in {row.fit_id}")
    for fit_id, group in preprocessing.groupby("fit_id"):
        fit = fits.loc[fits["fit_id"].eq(fit_id)].iloc[0]
        if len(group) != fit["feature_count_requested"]:
            raise ValueError(f"preprocessing metadata count differs for {fit_id}")
        if group["fit_partition"].ne("train").any():
            raise ValueError(f"preprocessing is not TRAIN-only for {fit_id}")
        policy = fit["ablation_policy"]
        expected = set(QUANTITATIVE_BASELINE_FEATURES)
        if policy != "full":
            expected -= set(FEATURE_FAMILIES[policy.removeprefix("without_")])
        if set(group["original_feature"]) != expected:
            raise ValueError(f"preprocessing feature subset differs for {fit_id}")
    liquidity = preprocessing.loc[preprocessing["ablation_policy"].eq("without_liquidity_volume")]
    if liquidity["original_feature"].str.contains("avg_dollar_volume").any():
        raise ValueError("liquidity ablation recreated removed ADV features")
    fit_effective = fits.set_index("fit_id")["feature_count_effective"]
    predicted_effective = predictions["fit_id"].map(fit_effective)
    if not predicted_effective.equals(predictions["feature_count_effective"]):
        raise ValueError("prediction effective feature counts differ from fits")
    for policy in ABLATION_POLICIES:
        _check_schedule(fits, predictions, policy)
        if set(metrics[policy].get("by_year", {})) != YEARS:
            raise ValueError(f"annual metrics incomplete for {policy}")
    rows = {row.ablation_policy: row for row in summary_frame.itertuples(index=False)}
    for policy in ABLATION_POLICIES:
        delta = policy_deltas(policy, metrics)
        row = rows[policy]
        for name, value in delta.items():
            if abs(float(getattr(row, name)) - value) > 1e-15:
                raise ValueError(f"non-reproducible {name} for {policy}")
        if policy == "full":
            if row.classification != "reference" or row.strong_contributor or row.harmful_candidate:
                raise ValueError("full row classification is invalid")
            continue
        expected_class = classify_ablation(delta["delta_mean_ic_vs_full"])
        flags = diagnostic_flags(
            delta_mean_ic=delta["delta_mean_ic_vs_full"],
            delta_worst_year_ic=delta["delta_worst_year_ic_vs_full"],
            delta_icir=delta["delta_icir_vs_full"],
            delta_top10_uplift=delta["delta_top10_uplift_vs_full"],
        )
        if row.classification != expected_class:
            raise ValueError(f"classification differs for {policy}")
        if bool(row.strong_contributor) != flags["strong_contributor"]:
            raise ValueError(f"strong-contributor flag differs for {policy}")
        if bool(row.harmful_candidate) != flags["harmful_candidate"]:
            raise ValueError(f"harmful-candidate flag differs for {policy}")
    sorted_deltas = summary_frame["delta_mean_ic_vs_full"].astype(float).tolist()
    if sorted_deltas != sorted(sorted_deltas):
        raise ValueError("summary is not ordered by delta mean IC")
    reference = json.loads(REFERENCE.read_text(encoding="utf-8"))
    reference_metrics = _metric_vector(reference["window_results"]["expanding"]["metrics"])
    full_metrics = _metric_vector(metrics["full"])
    differences = {name: abs(full_metrics[name] - reference_metrics[name]) for name in reference_metrics}
    if any(value > REAL_REPRO_TOLERANCE for value in differences.values()):
        raise ValueError("full does not reproduce Phase 3D.5")
    persisted_check = summary.get("full_reproduction_check", {})
    if persisted_check.get("passed") is not True or persisted_check.get("absolute_differences") != differences:
        raise ValueError("persisted reproduction check differs")
    harmful = sorted(
        row.removed_family for row in summary_frame.itertuples(index=False)
        if row.ablation_policy != "full" and bool(row.harmful_candidate)
    )
    if bool(summary.get("confirmation_subset_warranted")) != bool(harmful):
        raise ValueError("3D.6.1 warrant flag differs from harmful candidates")
    if summary.get("official_feature_set_changed") is not False:
        raise ValueError("summary claims an official feature-set mutation")
    if summary.get("adaptive_second_round_run") is not False:
        raise ValueError("summary claims an adaptive second round")
    if any("test" in path.name.lower() for path in ROOT.rglob("*") if path.is_file()):
        raise ValueError("TEST-named artifact found in Phase 3D.6 output")
    print(json.dumps({
        "status": "passed",
        "families": len(FEATURE_FAMILIES),
        "policies": len(ABLATION_POLICIES),
        "fits": len(fits),
        "prediction_rows": len(predictions),
        "prediction_date_min": str(dates.min()),
        "prediction_date_max": str(dates.max()),
        "full_reproduction_absolute_differences": differences,
        "confirmation_subset_warranted": bool(harmful),
        "test_used": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
