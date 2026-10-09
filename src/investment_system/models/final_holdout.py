"""One-shot Phase 3E.2 final-holdout execution contracts and pure logic."""
from __future__ import annotations

from datetime import date, datetime, timezone
import json
import os
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.linear_model import Ridge

from investment_system.data.calendar import TradingCalendar
from investment_system.features.targets import TARGET_COLUMNS, TARGET_METADATA_COLUMNS
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.holdout_protocol import (
    AUTHORIZED_CANDIDATE_FINGERPRINT,
    AUTHORIZED_DATA_SNAPSHOT_FINGERPRINT,
    AUTHORIZED_HOLDOUT_PROTOCOL_FINGERPRINT,
    EXPECTED_RF_PARAMETERS,
    NOMINAL_TEST_START,
    PROTOCOL_ID,
    PROTOCOL_STATUS,
    classify_absolute_holdout,
    classify_rf_vs_ridge,
    protocol_consistency_checks,
)
from investment_system.models.metrics import (
    cross_sectional_percentile_rank,
    ranking_metrics,
    regression_metrics,
)
from investment_system.models.preprocessing import BaselinePreprocessor, PREPROCESSING_VERSION
from investment_system.models.tree_preprocessing import TREE_PREPROCESSING_VERSION, TreePreprocessor
from investment_system.models.walkforward import (
    ELIGIBILITY_COLUMN,
    INITIAL_TRAIN_START,
    RANK_COLUMN,
    TARGET_COLUMN,
    TARGET_END_COLUMN,
    build_walkforward_schedule,
    validate_schedule,
    xnys_sessions,
)

EVALUATION_ID = "final-holdout-evaluation-v1"
NOMINAL_TEST_END = date(2026, 10, 5)
AUTHORIZED_MODEL_IDENTITIES = (
    "development-candidate-v1", "ridge_100", "momentum_20d",
)


def _boolean(values: pd.Series) -> pd.Series:
    return values.astype("boolean").fillna(False).astype(bool)


def preflight_checks(
    candidate: Mapping[str, Any], protocol: Mapping[str, Any],
    snapshot: Mapping[str, Any], summary: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate every frozen gate without touching Feature or Target Stores."""
    canonical = protocol_consistency_checks(candidate, snapshot, protocol)
    observations = {
        "candidate_id": candidate.get("candidate_id") == "development-candidate-v1",
        "candidate_fingerprint": candidate.get("candidate_fingerprint") == AUTHORIZED_CANDIDATE_FINGERPRINT,
        "protocol_id": protocol.get("protocol_id") == PROTOCOL_ID,
        "protocol_fingerprint": protocol.get("holdout_protocol_fingerprint") == AUTHORIZED_HOLDOUT_PROTOCOL_FINGERPRINT,
        "snapshot_fingerprint": snapshot.get("data_snapshot_fingerprint") == AUTHORIZED_DATA_SNAPSHOT_FINGERPRINT,
        "protocol_status": protocol.get("protocol_status") == PROTOCOL_STATUS,
        "ready_to_open_test": summary.get("ready_to_open_test") is True,
        "test_used": summary.get("test_used") is False,
        "test_opened": summary.get("test_opened") is False,
        "holdout_executed": summary.get("holdout_executed") is False,
        "nominal_test_start": protocol.get("test_range", {}).get("nominal_test_start") == NOMINAL_TEST_START,
        "nominal_test_end": protocol.get("test_range", {}).get("nominal_test_end") == str(NOMINAL_TEST_END),
        "candidate_feature_hash": candidate.get("feature_names_hash") == "55f32fa21661f33134746a577aef3e7da7816d8a33d02f52f8b1ee2d0a87501c",
        "protocol_consistency": canonical["passed"] is True,
    }
    failed = [name for name, passed in observations.items() if not passed]
    return {"passed": not failed, "checks": observations, "failed_checks": failed}


def opening_identity(
    candidate: Mapping[str, Any], protocol: Mapping[str, Any],
    snapshot: Mapping[str, Any], *, opened_at: str,
) -> dict[str, Any]:
    return {
        "evaluation_id": EVALUATION_ID,
        "candidate_id": candidate["candidate_id"],
        "candidate_fingerprint": candidate["candidate_fingerprint"],
        "protocol_id": protocol["protocol_id"],
        "holdout_protocol_fingerprint": protocol["holdout_protocol_fingerprint"],
        "data_snapshot_fingerprint": snapshot["data_snapshot_fingerprint"],
        "nominal_test_start": protocol["test_range"]["nominal_test_start"],
        "nominal_test_end": protocol["test_range"]["nominal_test_end"],
        "opened_at": opened_at,
        "execution_type": "first_official_evaluation",
        "test_opened": True,
    }


def validate_existing_opening(record: Mapping[str, Any], expected: Mapping[str, Any]) -> None:
    """Reject any attempt to reopen under a changed identity or nominal range."""
    immutable = (
        "evaluation_id", "candidate_id", "candidate_fingerprint", "protocol_id",
        "holdout_protocol_fingerprint", "data_snapshot_fingerprint",
        "nominal_test_start", "nominal_test_end",
    )
    mismatches = [key for key in immutable if record.get(key) != expected.get(key)]
    if mismatches:
        raise ValueError(f"opening record identity mismatch: {mismatches}")
    if record.get("test_opened") is not True or not record.get("opened_at"):
        raise ValueError("opening record is not a durable opened state")


def persist_opening_record(
    path: Path, candidate: Mapping[str, Any], protocol: Mapping[str, Any],
    snapshot: Mapping[str, Any], *, now: Callable[[], datetime] | None = None,
) -> tuple[dict[str, Any], str]:
    """Atomically open once; an existing exact record is resume-only."""
    timestamp = (now or (lambda: datetime.now(timezone.utc)))().isoformat()
    expected = opening_identity(candidate, protocol, snapshot, opened_at=timestamp)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
        validate_existing_opening(existing, expected)
        return existing, "reproduction_or_resume"
    encoded = (json.dumps(expected, indent=2) + "\n").encode("utf-8")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError:
        existing = json.loads(path.read_text(encoding="utf-8"))
        validate_existing_opening(existing, expected)
        return existing, "reproduction_or_resume"
    with os.fdopen(descriptor, "wb") as handle:
        handle.write(encoded)
        handle.flush()
        os.fsync(handle.fileno())
    return expected, "first_official_evaluation"


def open_before_load(
    opening_path: Path, candidate: Mapping[str, Any], protocol: Mapping[str, Any],
    snapshot: Mapping[str, Any], loader: Callable[[], tuple[pd.DataFrame, pd.DataFrame]],
    *, now: Callable[[], datetime] | None = None,
) -> tuple[dict[str, Any], str, pd.DataFrame, pd.DataFrame]:
    """Enforce durable opening before the first callback capable of reading TEST."""
    record, execution_type = persist_opening_record(
        opening_path, candidate, protocol, snapshot, now=now,
    )
    features, targets = loader()
    return record, execution_type, features, targets


def build_holdout_frame(
    features: pd.DataFrame, targets: pd.DataFrame, *, nominal_end: date = NOMINAL_TEST_END,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Join exact frozen inputs and resolve the observable 20d tail."""
    keys = ["ticker", "decision_date"]
    for name, frame in (("features", features), ("targets", targets)):
        if frame.duplicated(keys).any():
            raise ValueError(f"duplicate ticker + decision_date in {name}")
    if tuple(name for name in QUANTITATIVE_BASELINE_FEATURES if name in features) != QUANTITATIVE_BASELINE_FEATURES:
        raise ValueError("holdout requires the exact ordered 52-feature allowlist")
    if (set(TARGET_COLUMNS) | set(TARGET_METADATA_COLUMNS)) & set(QUANTITATIVE_BASELINE_FEATURES):
        raise ValueError("target data cannot enter model features")
    feature_columns = [
        *keys, "model_eligible", "feature_corporate_action_contaminated",
        *QUANTITATIVE_BASELINE_FEATURES,
    ]
    target_columns = [*keys, TARGET_COLUMN, RANK_COLUMN, TARGET_END_COLUMN, ELIGIBILITY_COLUMN]
    joined = features[feature_columns].merge(
        targets[target_columns], on=keys, how="inner", validate="one_to_one",
    )
    joined["decision_date"] = pd.to_datetime(joined["decision_date"]).dt.date
    joined[TARGET_END_COLUMN] = pd.to_datetime(joined[TARGET_END_COLUMN], errors="coerce").dt.date
    base = (
        _boolean(joined["model_eligible"])
        & ~_boolean(joined["feature_corporate_action_contaminated"])
        & joined["decision_date"].between(INITIAL_TRAIN_START, nominal_end)
    )
    complete = (
        base & _boolean(joined[ELIGIBILITY_COLUMN])
        & joined[TARGET_COLUMN].notna() & joined[RANK_COLUMN].notna()
        & joined[TARGET_END_COLUMN].notna()
        & joined[TARGET_END_COLUMN].le(nominal_end)
    )
    test_complete = complete & joined["decision_date"].ge(date.fromisoformat(NOMINAL_TEST_START))
    if not test_complete.any():
        raise ValueError("no fully observable TEST targets exist")
    effective_end = max(joined.loc[test_complete, "decision_date"])
    tail_base = base & joined["decision_date"].gt(effective_end)
    tail_dates = sorted(joined.loc[tail_base, "decision_date"].unique())
    result = joined.loc[complete & joined["decision_date"].le(effective_end), [
        *keys, *QUANTITATIVE_BASELINE_FEATURES, TARGET_COLUMN, RANK_COLUMN, TARGET_END_COLUMN,
    ]].sort_values(["decision_date", "ticker"], kind="mergesort").reset_index(drop=True)
    diagnostics = {
        "nominal_test_end": str(nominal_end),
        "effective_test_end": str(effective_end),
        "excluded_incomplete_tail_decision_dates": [str(value) for value in tail_dates],
        "excluded_incomplete_tail_session_count": len(tail_dates),
        "excluded_incomplete_tail_row_count": int(tail_base.sum()),
    }
    return result, diagnostics


def _training_masks(frame: pd.DataFrame, prediction_start: date) -> tuple[pd.Series, pd.Series]:
    nominal = frame["decision_date"].ge(INITIAL_TRAIN_START) & frame["decision_date"].lt(prediction_start)
    purged = nominal & frame[TARGET_END_COLUMN].lt(prediction_start)
    if not purged.any() or frame.loc[purged, TARGET_END_COLUMN].max() >= prediction_start:
        raise ValueError("strict dynamic purge failed")
    return nominal, purged


def _model_contract(model_identity: str) -> tuple[Any, type[Any], str, dict[str, Any]]:
    if model_identity == "development-candidate-v1":
        params = dict(EXPECTED_RF_PARAMETERS)
        return RandomForestRegressor(**params), TreePreprocessor, TREE_PREPROCESSING_VERSION, params
    if model_identity == "ridge_100":
        params = {"alpha": 100.0}
        return Ridge(**params), BaselinePreprocessor, PREPROCESSING_VERSION, params
    raise ValueError(f"unauthorized fitted model identity: {model_identity}")


def run_annual_model(
    frame: pd.DataFrame, model_identity: str, calendar: TradingCalendar,
    *, test_start: date = date.fromisoformat(NOMINAL_TEST_START), effective_end: date,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run one exact annual expanding policy for RF or Ridge."""
    periods = build_walkforward_schedule(calendar, "annual", start=test_start, end=effective_end)
    validate_schedule(periods, xnys_sessions(calendar, test_start, effective_end))
    prediction_frames: list[pd.DataFrame] = []
    fits: list[dict[str, Any]] = []
    preprocessing_rows: list[dict[str, Any]] = []
    for period in periods:
        nominal, purged = _training_masks(frame, period.prediction_start)
        train = frame.loc[purged].reset_index(drop=True)
        predict = frame.loc[frame["decision_date"].isin(period.sessions)].reset_index(drop=True)
        if predict.empty:
            raise ValueError(f"annual TEST period has no evaluable rows: {period.prediction_start}")
        model, preprocessor_type, prep_version, hyperparameters = _model_contract(model_identity)
        fit_id = f"{model_identity}-annual-{period.prediction_start:%Y%m%d}"
        preprocessor = preprocessor_type(QUANTITATIVE_BASELINE_FEATURES)
        started = perf_counter()
        train_x = preprocessor.fit_transform(train.loc[:, QUANTITATIVE_BASELINE_FEATURES])
        model.fit(train_x, train[TARGET_COLUMN].astype(float))
        fit_seconds = perf_counter() - started
        prediction_started = perf_counter()
        scores = np.asarray(
            model.predict(preprocessor.transform(predict.loc[:, QUANTITATIVE_BASELINE_FEATURES])),
            dtype=float,
        )
        prediction_seconds = perf_counter() - prediction_started
        output = pd.DataFrame({
            "model_identity": model_identity,
            "ticker": predict["ticker"].to_numpy(),
            "decision_date": predict["decision_date"].to_numpy(),
            "actual_return_20d": predict[TARGET_COLUMN].to_numpy(dtype=float),
            "actual_rank_20d": predict[RANK_COLUMN].to_numpy(dtype=float),
            "target_end_date_20d": predict[TARGET_END_COLUMN].to_numpy(),
            "predicted_return": scores,
            "score": scores,
            "fit_id": fit_id,
            "year": period.prediction_start.year,
            "test_used": True,
        })
        output["predicted_rank"] = cross_sectional_percentile_rank(output["score"], output["decision_date"])
        prediction_frames.append(output)
        metadata = preprocessor.metadata()
        for row in metadata["features"]:
            preprocessing_rows.append({
                "model_identity": model_identity, "fit_id": fit_id,
                "preprocessing_version": prep_version, **row,
            })
        fit_row = {
            "model_identity": model_identity, "fit_id": fit_id,
            "prediction_year": period.prediction_start.year,
            "prediction_start": period.prediction_start,
            "prediction_end": period.prediction_end,
            "training_start": INITIAL_TRAIN_START,
            "training_end": train["decision_date"].max(),
            "rows_before_purge": int(nominal.sum()),
            "rows_after_purge": int(purged.sum()),
            "purged_rows": int(nominal.sum() - purged.sum()),
            "max_train_target_end_date": train[TARGET_END_COLUMN].max(),
            "previous_test_year_training_rows": int(
                (train["decision_date"] >= date.fromisoformat(NOMINAL_TEST_START)).sum()
            ),
            "preprocessing_version": prep_version,
            "hyperparameters": json.dumps(hyperparameters, sort_keys=True),
            "fit_seconds": fit_seconds,
            "prediction_seconds": prediction_seconds,
            "test_used": True,
        }
        fits.append(fit_row)
        if progress:
            progress(fit_row)
    return (
        pd.concat(prediction_frames, ignore_index=True),
        pd.DataFrame(fits),
        pd.DataFrame(preprocessing_rows),
    )


def momentum_predictions(frame: pd.DataFrame, *, test_start: date, effective_end: date) -> pd.DataFrame:
    rows = frame.loc[frame["decision_date"].between(test_start, effective_end)].copy()
    scores = rows["momentum_20d"].astype(float)
    result = pd.DataFrame({
        "model_identity": "momentum_20d", "ticker": rows["ticker"],
        "decision_date": rows["decision_date"], "actual_return_20d": rows[TARGET_COLUMN],
        "actual_rank_20d": rows[RANK_COLUMN], "predicted_return": np.nan,
        "target_end_date_20d": rows[TARGET_END_COLUMN],
        "score": scores, "fit_id": None,
        "year": pd.to_datetime(rows["decision_date"]).dt.year,
        "test_used": True,
    }).reset_index(drop=True)
    result["predicted_rank"] = cross_sectional_percentile_rank(result["score"], result["decision_date"])
    return result


def _partial_year(calendar: TradingCalendar, year: int, effective_end: date) -> bool:
    sessions = xnys_sessions(calendar, date(year, 1, 1), date(year, 12, 31))
    return effective_end < sessions[-1]


def evaluate_predictions(
    predictions: pd.DataFrame, calendar: TradingCalendar, effective_end: date,
) -> dict[str, Any]:
    """Calculate the frozen overall, annual, and cross-year metrics."""
    ranking = ranking_metrics(
        predictions["actual_rank_20d"], predictions["actual_return_20d"],
        predictions["score"], predictions["decision_date"],
    )
    identity = str(predictions["model_identity"].iloc[0])
    regression = None
    if identity != "momentum_20d":
        regression = regression_metrics(
            predictions["actual_return_20d"], predictions["predicted_return"],
            predictions["decision_date"],
        )
    annual: dict[str, Any] = {}
    annual_means: list[float] = []
    years = pd.to_datetime(predictions["decision_date"]).dt.year
    for year in sorted(years.unique()):
        subset = predictions.loc[years.eq(year)].reset_index(drop=True)
        values = ranking_metrics(
            subset["actual_rank_20d"], subset["actual_return_20d"],
            subset["score"], subset["decision_date"],
        )
        mean_ic = values["rank_ic"]["mean"]
        annual[str(year)] = {
            "mean_rank_ic": mean_ic,
            "median_rank_ic": values["rank_ic"]["median"],
            "icir": values["rank_ic"]["icir"],
            "pct_positive_ic": values["rank_ic"]["pct_positive"],
            "top10_uplift": values["top10"]["average_top10_uplift"],
            "decision_date_count": int(subset["decision_date"].nunique()),
            "partial_year": _partial_year(calendar, int(year), effective_end),
        }
        if mean_ic is not None:
            annual_means.append(float(mean_ic))
    stability = {
        "worst_year_ic": min(annual_means), "best_year_ic": max(annual_means),
        "year_ic_std": float(np.std(annual_means, ddof=1)) if len(annual_means) > 1 else None,
        "positive_years": int(sum(value > 0 for value in annual_means)),
        "negative_years": int(sum(value < 0 for value in annual_means)),
        "evaluable_years": len(annual_means),
        "positive_year_share": float(sum(value > 0 for value in annual_means) / len(annual_means)),
    }
    return {
        "model_identity": identity,
        "rows": int(len(predictions)),
        "decision_dates": int(predictions["decision_date"].nunique()),
        "ranking": ranking,
        "regression": regression,
        "annual": annual,
        "stability": stability,
    }


def classification_report(
    rf_metrics: Mapping[str, Any], ridge_metrics: Mapping[str, Any],
    momentum_metrics: Mapping[str, Any], *, development_mean_ic: float,
) -> dict[str, Any]:
    rank = rf_metrics["ranking"]
    stability = rf_metrics["stability"]
    mean_ic = float(rank["rank_ic"]["mean"])
    top10 = float(rank["top10"]["average_top10_uplift"])
    absolute = classify_absolute_holdout(
        mean_rank_ic=mean_ic,
        worst_year_ic=float(stability["worst_year_ic"]),
        positive_years=int(stability["positive_years"]),
        evaluable_years=int(stability["evaluable_years"]),
        top10_uplift=top10,
    )
    ridge_ic = float(ridge_metrics["ranking"]["rank_ic"]["mean"])
    momentum_ic = float(momentum_metrics["ranking"]["rank_ic"]["mean"])
    rules = {
        "hard_fail_mean_ic_le_0": mean_ic <= 0,
        "fail_mean_ic_between_0_and_0_01": 0 < mean_ic < 0.01,
        "fail_nonpositive_top10_and_mean_ic_below_0_03": top10 <= 0 and mean_ic < 0.03,
        "pass_mean_ic_ge_0_03": mean_ic >= 0.03,
        "pass_worst_year_gt_minus_0_01": float(stability["worst_year_ic"]) > -0.01,
        "pass_positive_year_share_ge_0_50": float(stability["positive_year_share"]) >= 0.50,
        "pass_top10_uplift_gt_0": top10 > 0,
    }
    return {
        "absolute_status": absolute,
        "exact_unrounded_inputs": {
            "mean_rank_ic": mean_ic, "worst_year_ic": stability["worst_year_ic"],
            "positive_year_share": stability["positive_year_share"], "top10_uplift": top10,
        },
        "rule_evaluations": rules,
        "rf_vs_ridge": {
            "rf_mean_ic": mean_ic, "ridge_mean_ic": ridge_ic,
            "delta_rf_vs_ridge_ic": mean_ic - ridge_ic,
            "relative_classification": classify_rf_vs_ridge(
                rf_mean_rank_ic=mean_ic, ridge_mean_rank_ic=ridge_ic,
            ),
        },
        "momentum_comparison": {
            "rf_mean_ic": mean_ic, "momentum_mean_ic": momentum_ic,
            "delta_rf_vs_momentum_ic": mean_ic - momentum_ic,
            "changes_absolute_status": False,
        },
        "development_comparison": {
            "development_mean_ic": development_mean_ic,
            "delta_holdout_vs_development": mean_ic - development_mean_ic,
            "holdout_mean_ic_divided_by_development_mean_ic": mean_ic / development_mean_ic,
            "diagnostic_only": True,
        },
        "no_post_hoc_threshold_change": True,
    }


def validate_prediction_keys(predictions: pd.DataFrame) -> None:
    identities = set(predictions["model_identity"])
    if identities != set(AUTHORIZED_MODEL_IDENTITIES):
        raise ValueError(f"prediction artifact contains unauthorized identities: {identities}")
    key_sets = {
        identity: set(map(tuple, group[["ticker", "decision_date"]].to_numpy()))
        for identity, group in predictions.groupby("model_identity")
    }
    reference = key_sets["development-candidate-v1"]
    if any(values != reference for values in key_sets.values()):
        raise ValueError("candidate, Ridge, and momentum prediction keys differ")
    if predictions.duplicated(["model_identity", "ticker", "decision_date"]).any():
        raise ValueError("duplicate prediction identity + ticker + decision_date")
