"""Post-open validator for the one-shot Phase 3E.2 result."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from typing import Any

import pandas as pd

from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.models.final_holdout import (
    AUTHORIZED_MODEL_IDENTITIES,
    EVALUATION_ID,
    NOMINAL_TEST_END,
    classification_report,
    evaluate_predictions,
    opening_identity,
    preflight_checks,
    validate_existing_opening,
    validate_prediction_keys,
)
from investment_system.models.holdout_protocol import (
    AUTHORIZED_CANDIDATE_FINGERPRINT,
    AUTHORIZED_DATA_SNAPSHOT_FINGERPRINT,
    AUTHORIZED_HOLDOUT_PROTOCOL_FINGERPRINT,
    EXPECTED_RF_PARAMETERS,
)
from investment_system.models.walkforward import build_walkforward_schedule

PROTOCOL_ROOT = Path("data/reports/models/phase3e/protocol")
OUTPUT_ROOT = Path("data/reports/models/phase3e/holdout")
CANDIDATE_PATH = Path("data/reports/models/phase3d/final_candidate/candidate_contract.json")
DEVELOPMENT_METRICS_PATH = Path(
    "data/reports/models/phase3d/final_candidate/development_metrics.json"
)
REQUIRED_FILES = {
    "opening_record.json", "evaluation_manifest.json", "fits.parquet",
    "preprocessing.parquet", "predictions.parquet", "holdout_metrics.json",
    "annual_metrics.json", "classification.json", "phase3e2_summary.json",
}


def _json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required final-holdout artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    actual_files = {path.name for path in OUTPUT_ROOT.iterdir() if path.is_file()}
    if actual_files != REQUIRED_FILES:
        raise ValueError(
            f"final-holdout artifact set differs: expected={sorted(REQUIRED_FILES)}, "
            f"observed={sorted(actual_files)}"
        )
    candidate = _json(CANDIDATE_PATH)
    protocol = _json(PROTOCOL_ROOT / "holdout_protocol.json")
    snapshot = _json(PROTOCOL_ROOT / "snapshot_contract.json")
    phase3e1 = _json(PROTOCOL_ROOT / "phase3e1_summary.json")
    if not preflight_checks(candidate, protocol, snapshot, phase3e1)["passed"]:
        raise ValueError("frozen preflight identities no longer pass")

    opening = _json(OUTPUT_ROOT / "opening_record.json")
    manifest = _json(OUTPUT_ROOT / "evaluation_manifest.json")
    persisted_metrics = _json(OUTPUT_ROOT / "holdout_metrics.json")
    persisted_annual = _json(OUTPUT_ROOT / "annual_metrics.json")
    persisted_classification = _json(OUTPUT_ROOT / "classification.json")
    summary = _json(OUTPUT_ROOT / "phase3e2_summary.json")
    expected_opening = opening_identity(
        candidate, protocol, snapshot, opened_at=opening["opened_at"],
    )
    validate_existing_opening(opening, expected_opening)
    if opening != expected_opening:
        raise ValueError("opening record contains mutable or unexpected fields")
    if manifest["opened_at"] != opening["opened_at"]:
        raise ValueError("opening timestamp changed after first TEST access")

    exact_manifest = {
        "evaluation_id": EVALUATION_ID,
        "candidate_fingerprint": AUTHORIZED_CANDIDATE_FINGERPRINT,
        "holdout_protocol_fingerprint": AUTHORIZED_HOLDOUT_PROTOCOL_FINGERPRINT,
        "data_snapshot_fingerprint": AUTHORIZED_DATA_SNAPSHOT_FINGERPRINT,
        "nominal_test_start": "2022-01-03",
        "nominal_test_end": str(NOMINAL_TEST_END),
        "calendar": "XNYS",
        "model_identities": list(AUTHORIZED_MODEL_IDENTITIES),
        "test_used": True, "test_opened": True, "holdout_executed": True,
        "portfolio_backtest_run": False, "adaptive_reruns": False,
    }
    for key, expected in exact_manifest.items():
        if manifest.get(key) != expected:
            raise ValueError(f"evaluation manifest invariant failed: {key}")
    if manifest.get("execution_type") not in {"first_official_evaluation", "reproduction_or_resume"}:
        raise ValueError("invalid execution type")
    effective_end = date.fromisoformat(manifest["effective_test_end"])
    if not date(2022, 1, 3) <= effective_end <= NOMINAL_TEST_END:
        raise ValueError("effective TEST end lies outside the frozen nominal range")

    predictions = pd.read_parquet(OUTPUT_ROOT / "predictions.parquet")
    fits = pd.read_parquet(OUTPUT_ROOT / "fits.parquet")
    preprocessing = pd.read_parquet(OUTPUT_ROOT / "preprocessing.parquet")
    predictions["decision_date"] = pd.to_datetime(predictions["decision_date"]).dt.date
    predictions["target_end_date_20d"] = pd.to_datetime(
        predictions["target_end_date_20d"],
    ).dt.date
    for column in ("prediction_start", "prediction_end", "training_start", "training_end", "max_train_target_end_date"):
        fits[column] = pd.to_datetime(fits[column]).dt.date
    validate_prediction_keys(predictions)
    if not predictions["test_used"].eq(True).all():
        raise ValueError("prediction artifact contains non-TEST rows")
    if predictions["decision_date"].min() != date(2022, 1, 3):
        raise ValueError("prediction start differs from frozen TEST start")
    if predictions["decision_date"].max() != effective_end:
        raise ValueError("prediction end differs from effective TEST end")
    if predictions["target_end_date_20d"].gt(NOMINAL_TEST_END).any():
        raise ValueError("prediction artifact contains incomplete 20d targets")
    if predictions[["actual_return_20d", "actual_rank_20d", "score"]].isna().any().any():
        raise ValueError("prediction artifact contains missing evaluation values")
    expected_partial = predictions["year"].eq(effective_end.year)
    if not predictions["partial_year"].eq(expected_partial).all():
        raise ValueError("partial-year prediction flags differ")

    calendar = XNYSTradingCalendar()
    schedule = build_walkforward_schedule(
        calendar, "annual", start=date(2022, 1, 3), end=effective_end,
    )
    expected_starts = {period.prediction_start for period in schedule}
    if set(fits["model_identity"]) != {"development-candidate-v1", "ridge_100"}:
        raise ValueError("fits contain an unauthorized model")
    for identity, group in fits.groupby("model_identity"):
        if set(group["prediction_start"]) != expected_starts or len(group) != len(schedule):
            raise ValueError(f"annual schedule differs for {identity}")
        if not group["training_start"].eq(date(2010, 1, 4)).all():
            raise ValueError(f"training start differs for {identity}")
        if not (group["max_train_target_end_date"] < group["prediction_start"]).all():
            raise ValueError(f"strict purge failed for {identity}")
        if not group["test_used"].eq(True).all():
            raise ValueError(f"fit TEST flag failed for {identity}")
        if not group.sort_values("prediction_start")["rows_after_purge"].is_monotonic_increasing:
            raise ValueError(f"expanding row count failed for {identity}")
    rf_fits = fits.loc[fits["model_identity"].eq("development-candidate-v1")]
    ridge_fits = fits.loc[fits["model_identity"].eq("ridge_100")]
    expected_rf = json.dumps(EXPECTED_RF_PARAMETERS, sort_keys=True)
    if not rf_fits["hyperparameters"].eq(expected_rf).all():
        raise ValueError("RF parameters differ from frozen candidate")
    if not rf_fits["preprocessing_version"].eq("tree-preprocessing-v1").all():
        raise ValueError("RF preprocessing differs")
    if not ridge_fits["hyperparameters"].eq('{"alpha": 100.0}').all():
        raise ValueError("Ridge alpha differs")
    if not ridge_fits["preprocessing_version"].eq("baseline-standard-v1").all():
        raise ValueError("Ridge preprocessing differs")
    if not preprocessing.groupby(["model_identity", "fit_id"]).size().eq(52).all():
        raise ValueError("preprocessing metadata does not cover exactly 52 features per fit")
    if set(preprocessing["model_identity"]) != {"development-candidate-v1", "ridge_100"}:
        raise ValueError("preprocessing contains unauthorized identity")

    recomputed_metrics = {
        identity: evaluate_predictions(
            predictions.loc[predictions["model_identity"].eq(identity)].reset_index(drop=True),
            calendar, effective_end,
        )
        for identity in AUTHORIZED_MODEL_IDENTITIES
    }
    if recomputed_metrics != persisted_metrics:
        raise ValueError("holdout metrics are not reproducible from predictions")
    recomputed_annual = {
        identity: values["annual"] for identity, values in recomputed_metrics.items()
    }
    if recomputed_annual != persisted_annual:
        raise ValueError("annual metrics are not reproducible")
    development_mean = float(_json(DEVELOPMENT_METRICS_PATH)["mean_rank_ic"])
    recomputed_classification = classification_report(
        recomputed_metrics["development-candidate-v1"], recomputed_metrics["ridge_100"],
        recomputed_metrics["momentum_20d"], development_mean_ic=development_mean,
    )
    if recomputed_classification != persisted_classification:
        raise ValueError("classification is not reproducible under the frozen thresholds")

    summary_invariants = {
        "test_used": True, "test_opened": True, "holdout_executed": True,
        "portfolio_backtest_run": False, "unauthorized_models_evaluated": False,
        "thresholds_changed_after_opening": False,
        "candidate_changed_after_opening": False,
        "production_ready": False, "approved_for_trading": False,
    }
    for key, expected in summary_invariants.items():
        observed = summary.get(key, manifest.get(key))
        if observed != expected:
            raise ValueError(f"summary invariant failed: {key}")
    tail = summary["test_range"]
    if tail["effective_test_end"] != str(effective_end):
        raise ValueError("tail diagnostics effective end differs")
    if tail["excluded_incomplete_tail_session_count"] != len(tail["excluded_incomplete_tail_decision_dates"]):
        raise ValueError("incomplete-tail session count differs")
    forbidden_suffixes = {".pkl", ".pickle", ".joblib"}
    if any(path.suffix.lower() in forbidden_suffixes for path in OUTPUT_ROOT.rglob("*")):
        raise ValueError("serialized model artifact exists")
    if any(name in actual_files for name in ("portfolio_metrics.json", "portfolio_backtest.json")):
        raise ValueError("portfolio evaluation artifact exists")

    print(json.dumps({
        "status": "passed", "evaluation_id": EVALUATION_ID,
        "execution_type": manifest["execution_type"],
        "absolute_status": persisted_classification["absolute_status"],
        "effective_test_end": str(effective_end), "fit_count": int(len(fits)),
        "prediction_rows": int(len(predictions)),
        "test_used": True, "test_opened": True, "holdout_executed": True,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
