"""Execute the one-shot Phase 3E.2 holdout under the frozen protocol."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from investment_system.core.config import load_settings
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.final_holdout import (
    AUTHORIZED_MODEL_IDENTITIES,
    EVALUATION_ID,
    ELIGIBILITY_COLUMN,
    NOMINAL_TEST_END,
    RANK_COLUMN,
    TARGET_COLUMN,
    TARGET_END_COLUMN,
    build_holdout_frame,
    classification_report,
    evaluate_predictions,
    momentum_predictions,
    open_before_load,
    preflight_checks,
    run_annual_model,
    validate_prediction_keys,
)

PROTOCOL_ROOT = Path("data/reports/models/phase3e/protocol")
OUTPUT_ROOT = Path("data/reports/models/phase3e/holdout")
CANDIDATE_PATH = Path("data/reports/models/phase3d/final_candidate/candidate_contract.json")
DEVELOPMENT_METRICS_PATH = Path(
    "data/reports/models/phase3d/final_candidate/development_metrics.json"
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, default=str, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _write_parquet(path: Path, frame: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.stem + ".tmp.parquet")
    frame.to_parquet(temporary, index=False)
    temporary.replace(path)


def _year_files(files: list[Path]) -> list[Path]:
    return [
        path for path in files
        if 2010 <= int(path.parent.name.split("=")[1]) <= NOMINAL_TEST_END.year
    ]


def _load_frozen_snapshot() -> tuple[pd.DataFrame, pd.DataFrame]:
    """First TEST-capable read; caller must persist opening_record beforehand."""
    settings = load_settings()
    store = QuantitativeFeatureStore(
        settings.paths.features, settings.paths.features.parent / "targets",
    )
    feature_files = _year_files(sorted(store.features.glob("year=*/data.parquet")))
    target_files = _year_files(sorted(store.targets.glob("year=*/data.parquet")))
    if not feature_files or not target_files:
        raise ValueError("frozen Feature/Target Store snapshot is unavailable")
    feature_columns = [
        "ticker", "decision_date", "model_eligible",
        "feature_corporate_action_contaminated", *QUANTITATIVE_BASELINE_FEATURES,
    ]
    target_columns = [
        "ticker", "decision_date", TARGET_COLUMN, RANK_COLUMN,
        TARGET_END_COLUMN, ELIGIBILITY_COLUMN,
    ]
    features = pd.concat([
        pd.read_parquet(path, columns=feature_columns) for path in feature_files
    ], ignore_index=True)
    targets = pd.concat([
        pd.read_parquet(path, columns=target_columns) for path in target_files
    ], ignore_index=True)
    return features, targets


def _consequence(status: str) -> str:
    if status == "pass":
        return "frozen predictive candidate passed final holdout"
    if status == "marginal":
        return "frozen predictive candidate produced marginal final holdout result"
    return "frozen predictive candidate failed final holdout"


def _contracts() -> tuple[dict[str, Any], ...]:
    return (
        _read_json(CANDIDATE_PATH),
        _read_json(PROTOCOL_ROOT / "holdout_protocol.json"),
        _read_json(PROTOCOL_ROOT / "snapshot_contract.json"),
        _read_json(PROTOCOL_ROOT / "phase3e1_summary.json"),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--preflight-only", action="store_true")
    args = parser.parse_args()
    candidate, protocol, snapshot, phase3e1_summary = _contracts()
    preflight = preflight_checks(candidate, protocol, snapshot, phase3e1_summary)
    if not preflight["passed"]:
        raise ValueError(f"preflight failed before TEST opening: {preflight['failed_checks']}")
    if args.preflight_only:
        print(json.dumps({
            "status": "passed", "mode": "preflight_only", **preflight,
            "test_opened": False, "test_used": False, "holdout_executed": False,
        }))
        return 0

    opening, execution_type, features, targets = open_before_load(
        OUTPUT_ROOT / "opening_record.json", candidate, protocol, snapshot,
        _load_frozen_snapshot,
    )
    calendar = XNYSTradingCalendar()
    frame, tail = build_holdout_frame(features, targets)
    effective_end = date.fromisoformat(tail["effective_test_end"])
    test_start = date.fromisoformat(protocol["test_range"]["nominal_test_start"])

    def progress(row: dict[str, Any]) -> None:
        print(json.dumps({
            "fit_id": row["fit_id"], "rows_after_purge": row["rows_after_purge"],
            "fit_seconds": round(float(row["fit_seconds"]), 3), "test_used": True,
        }), flush=True)

    rf_predictions, rf_fits, rf_preprocessing = run_annual_model(
        frame, "development-candidate-v1", calendar,
        test_start=test_start, effective_end=effective_end, progress=progress,
    )
    ridge_predictions, ridge_fits, ridge_preprocessing = run_annual_model(
        frame, "ridge_100", calendar,
        test_start=test_start, effective_end=effective_end, progress=progress,
    )
    naive_predictions = momentum_predictions(
        frame, test_start=test_start, effective_end=effective_end,
    )
    predictions = pd.concat(
        [rf_predictions, ridge_predictions, naive_predictions], ignore_index=True,
    )
    predictions["partial_year"] = predictions["year"].eq(effective_end.year)
    validate_prediction_keys(predictions)
    fits = pd.concat([rf_fits, ridge_fits], ignore_index=True)
    preprocessing = pd.concat([rf_preprocessing, ridge_preprocessing], ignore_index=True)

    metrics = {
        identity: evaluate_predictions(
            predictions.loc[predictions["model_identity"].eq(identity)].reset_index(drop=True),
            calendar, effective_end,
        )
        for identity in AUTHORIZED_MODEL_IDENTITIES
    }
    development = _read_json(DEVELOPMENT_METRICS_PATH)
    development_mean_ic = float(development["mean_rank_ic"])
    classification = classification_report(
        metrics["development-candidate-v1"], metrics["ridge_100"],
        metrics["momentum_20d"], development_mean_ic=development_mean_ic,
    )
    annual_metrics = {
        identity: values["annual"] for identity, values in metrics.items()
    }
    status = classification["absolute_status"]
    executed_at = datetime.now(timezone.utc).isoformat()
    manifest = {
        "evaluation_id": EVALUATION_ID,
        "execution_type": execution_type,
        "candidate_fingerprint": candidate["candidate_fingerprint"],
        "holdout_protocol_fingerprint": protocol["holdout_protocol_fingerprint"],
        "data_snapshot_fingerprint": snapshot["data_snapshot_fingerprint"],
        "opened_at": opening["opened_at"], "executed_at": executed_at,
        "nominal_test_start": str(test_start),
        "nominal_test_end": str(NOMINAL_TEST_END),
        "effective_test_end": str(effective_end),
        "calendar": "XNYS",
        "model_identities": list(AUTHORIZED_MODEL_IDENTITIES),
        "test_used": True, "test_opened": True, "holdout_executed": True,
        "portfolio_backtest_run": False, "adaptive_reruns": False,
    }
    fit_timings = {
        identity: {
            "fit_count": int(len(group)),
            "total_fit_seconds": float(group["fit_seconds"].sum()),
            "mean_fit_seconds": float(group["fit_seconds"].mean()),
            "max_fit_seconds": float(group["fit_seconds"].max()),
        }
        for identity, group in fits.groupby("model_identity")
    }
    rf = metrics["development-candidate-v1"]
    summary = {
        **manifest,
        "candidate_id": candidate["candidate_id"],
        "test_range": tail,
        "prediction_rows": int(len(predictions)),
        "prediction_rows_per_identity": {
            key: int(value) for key, value in predictions.groupby("model_identity").size().items()
        },
        "prediction_decision_dates": int(rf["decision_dates"]),
        "fit_counts": {key: int(value) for key, value in fits.groupby("model_identity").size().items()},
        "fit_timings": fit_timings,
        "metrics": metrics,
        "annual_stability": annual_metrics,
        "classification": classification,
        "phase3_consequence": _consequence(status),
        "production_ready": False,
        "portfolio_profitability_demonstrated": False,
        "approved_for_trading": False,
        "unauthorized_models_evaluated": False,
        "thresholds_changed_after_opening": False,
        "candidate_changed_after_opening": False,
    }

    _write_parquet(OUTPUT_ROOT / "fits.parquet", fits)
    _write_parquet(OUTPUT_ROOT / "preprocessing.parquet", preprocessing)
    _write_parquet(OUTPUT_ROOT / "predictions.parquet", predictions)
    _write_json(OUTPUT_ROOT / "holdout_metrics.json", metrics)
    _write_json(OUTPUT_ROOT / "annual_metrics.json", annual_metrics)
    _write_json(OUTPUT_ROOT / "classification.json", classification)
    _write_json(OUTPUT_ROOT / "phase3e2_summary.json", summary)
    _write_json(OUTPUT_ROOT / "evaluation_manifest.json", manifest)
    print(json.dumps({
        "status": "passed", "evaluation_id": EVALUATION_ID,
        "execution_type": execution_type, "absolute_status": status,
        "effective_test_end": str(effective_end),
        "rf_mean_rank_ic": rf["ranking"]["rank_ic"]["mean"],
        "test_used": True, "test_opened": True, "holdout_executed": True,
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
