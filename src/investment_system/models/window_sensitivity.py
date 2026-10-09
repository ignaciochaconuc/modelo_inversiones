"""Causal training-window sensitivity for Phase 3D.5."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Literal

import numpy as np
import pandas as pd

from investment_system.data.calendar import TradingCalendar
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.metrics import cross_sectional_percentile_rank
from investment_system.models.tree_preprocessing import TreePreprocessor
from investment_system.models.walkforward import (
    INITIAL_TRAIN_START,
    RANK_COLUMN,
    TARGET_COLUMN,
    TARGET_END_COLUMN,
    WALKFORWARD_END,
    WALKFORWARD_START,
    Phase3DWalkForwardRunner,
    build_walkforward_schedule,
    model_age_bucket,
    policy_metrics,
    validate_schedule,
    xnys_sessions,
)

WindowPolicy = Literal["expanding", "trailing-8y", "trailing-5y"]
WINDOW_POLICIES: tuple[WindowPolicy, ...] = ("expanding", "trailing-8y", "trailing-5y")
WINDOW_IC_TOLERANCE = 0.003
MATERIAL_IMPROVEMENT_THRESHOLD = 0.005
REAL_REPRO_TOLERANCE = 1e-12


@dataclass(frozen=True)
class WindowSelection:
    raw_best_window: str
    selected_window: str
    best_mean_ic: float
    selected_mean_ic: float
    equivalent_windows: tuple[str, ...]
    rationale: str


def nominal_window_start(prediction_start: date, policy: WindowPolicy) -> date:
    """Return the calendar-based nominal start, floored at available history."""
    if policy == "expanding":
        return INITIAL_TRAIN_START
    years = {"trailing-8y": 8, "trailing-5y": 5}.get(policy)
    if years is None:
        raise ValueError(f"unsupported training-window policy: {policy}")
    candidate = (pd.Timestamp(prediction_start) - pd.DateOffset(years=years)).date()
    return max(INITIAL_TRAIN_START, candidate)


def window_training_masks(
    frame: pd.DataFrame, prediction_start: date, policy: WindowPolicy,
) -> tuple[pd.Series, pd.Series, date, date]:
    """Apply a date window and then strictly purge labels reaching activation."""
    window_start = nominal_window_start(prediction_start, policy)
    prior_dates = [value for value in frame["decision_date"].unique() if value < prediction_start]
    if not prior_dates:
        raise ValueError(f"no historical observations before {prediction_start}")
    nominal_end = max(prior_dates)
    nominal = frame["decision_date"].between(window_start, nominal_end)
    purged = nominal & (frame["decision_date"] < prediction_start) & (
        frame[TARGET_END_COLUMN] < prediction_start
    )
    if not purged.any():
        raise ValueError(f"dynamic purge leaves no training rows for {policy}/{prediction_start}")
    if frame.loc[purged, TARGET_END_COLUMN].max() >= prediction_start:
        raise ValueError("dynamic purge invariant failed")
    return nominal, purged, window_start, nominal_end


def _selection_key(policy: str, metrics: dict[str, dict[str, Any]]) -> tuple[float, ...]:
    values = metrics[policy]
    rank = values["overall"]["ranking"]["rank_ic"]
    return (
        float(rank["mean"]),
        float(values["stability"]["worst_year_ic"]),
        float(rank["icir"]),
        float(rank["pct_positive"]),
        float(values["overall"]["ranking"]["top10"]["average_top10_uplift"]),
        -float(WINDOW_POLICIES.index(policy)),
    )


def select_training_window(metrics: dict[str, dict[str, Any]]) -> WindowSelection:
    """Prefer expanding when its mean IC is within 0.003 of raw-best."""
    if set(metrics) != set(WINDOW_POLICIES):
        raise ValueError("selection requires exactly the three Phase 3D.5 window policies")
    raw_best = max(WINDOW_POLICIES, key=lambda policy: _selection_key(policy, metrics))
    best_ic = float(metrics[raw_best]["overall"]["ranking"]["rank_ic"]["mean"])
    equivalent = tuple(
        policy for policy in WINDOW_POLICIES
        if float(metrics[policy]["overall"]["ranking"]["rank_ic"]["mean"])
        >= best_ic - WINDOW_IC_TOLERANCE
    )
    selected = "expanding" if "expanding" in equivalent else raw_best
    selected_ic = float(metrics[selected]["overall"]["ranking"]["rank_ic"]["mean"])
    if selected == "expanding":
        rationale = (
            f"expanding is within {WINDOW_IC_TOLERANCE:.3f} of raw-best {raw_best}; "
            "it uses all available evidence, avoids another temporal hyperparameter, "
            "and is operationally simpler"
        )
    else:
        rationale = (
            f"expanding is outside {WINDOW_IC_TOLERANCE:.3f} of raw-best {raw_best}; "
            "raw mean IC leads, with worst-year IC, ICIR, positive-IC share, and "
            "top10 uplift as ordered secondary tie-breaks"
        )
    return WindowSelection(
        raw_best_window=raw_best,
        selected_window=selected,
        best_mean_ic=best_ic,
        selected_mean_ic=selected_ic,
        equivalent_windows=equivalent,
        rationale=rationale,
    )


def window_deltas(metrics: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """Compare each trailing policy with the frozen expanding reference."""
    base = metrics["expanding"]
    base_rank = base["overall"]["ranking"]["rank_ic"]
    result: dict[str, dict[str, Any]] = {}
    for policy in ("trailing-8y", "trailing-5y"):
        current = metrics[policy]
        rank = current["overall"]["ranking"]["rank_ic"]
        delta_mean = float(rank["mean"] - base_rank["mean"])
        result[policy] = {
            "delta_mean_ic_vs_expanding": delta_mean,
            "delta_icir_vs_expanding": float(rank["icir"] - base_rank["icir"]),
            "delta_worst_year_ic_vs_expanding": float(
                current["stability"]["worst_year_ic"] - base["stability"]["worst_year_ic"]
            ),
            "delta_top10_uplift_vs_expanding": float(
                current["overall"]["ranking"]["top10"]["average_top10_uplift"]
                - base["overall"]["ranking"]["top10"]["average_top10_uplift"]
            ),
            "material_improvement_vs_expanding": bool(
                delta_mean >= MATERIAL_IMPROVEMENT_THRESHOLD
                or np.isclose(
                    delta_mean, MATERIAL_IMPROVEMENT_THRESHOLD, rtol=0.0, atol=1e-15,
                )
            ),
        }
    return result


def interpret_window_results(
    metrics: dict[str, dict[str, Any]], selection: WindowSelection,
) -> dict[str, Any]:
    """Classify the result without treating small IC changes as concept drift."""
    deltas = window_deltas(metrics)
    stable_material = [
        policy for policy, values in deltas.items()
        if values["material_improvement_vs_expanding"]
        and values["delta_worst_year_ic_vs_expanding"] >= -WINDOW_IC_TOLERANCE
        and metrics[policy]["stability"]["year_ic_std"]
        <= metrics["expanding"]["stability"]["year_ic_std"] + WINDOW_IC_TOLERANCE
    ]
    if selection.selected_window == "expanding":
        case = "A"
        finding = "Expanding remains best or equivalent."
    elif stable_material:
        winner = selection.selected_window
        case = "B" if winner == "trailing-8y" else "C"
        finding = f"{winner} improves materially without clear stability deterioration."
    elif deltas[selection.selected_window]["delta_mean_ic_vs_expanding"] > 0:
        case = "D"
        finding = f"{selection.selected_window} improves average IC but worsens stability."
    else:
        case = "E"
        finding = "Window-sensitivity results are inconclusive."
    return {
        "case": case,
        "finding": finding,
        "concept_drift_evidence": bool(stable_material),
        "concept_drift_policy": stable_material[0] if stable_material else None,
        "stability_rule": (
            "material delta mean IC >= 0.005, delta worst-year IC >= -0.003, "
            "and year IC std increase <= 0.003"
        ),
    }


class Phase3DWindowSensitivityRunner:
    """Run annual frozen RF-Small while varying only the training window."""

    def __init__(self, output_root: str | Path, calendar: TradingCalendar) -> None:
        self.output_root = Path(output_root)
        self.calendar = calendar

    def run_policy(
        self, frame: pd.DataFrame, policy: WindowPolicy, *,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        if policy not in WINDOW_POLICIES:
            raise ValueError(f"unsupported training-window policy: {policy}")
        factory, preprocessor_type, preprocessing_version, hyperparameters = (
            Phase3DWalkForwardRunner._model_factory("rf-small")
        )
        if preprocessor_type is not TreePreprocessor:
            raise RuntimeError("RF-Small must use TreePreprocessor")
        eligible = frame["decision_date"].between(WALKFORWARD_START, WALKFORWARD_END)
        safe_end = min(WALKFORWARD_END, max(frame.loc[eligible, "decision_date"]))
        periods = build_walkforward_schedule(
            self.calendar, "annual", start=WALKFORWARD_START, end=safe_end,
        )
        validate_schedule(periods, xnys_sessions(self.calendar, WALKFORWARD_START, safe_end))
        prediction_frames: list[pd.DataFrame] = []
        fit_rows: list[dict[str, Any]] = []
        preprocessing_rows: list[dict[str, Any]] = []
        for period in periods:
            nominal, purged, window_start, nominal_end = window_training_masks(
                frame, period.prediction_start, policy,
            )
            train = frame.loc[purged].reset_index(drop=True)
            predict = frame.loc[frame["decision_date"].isin(period.sessions)].reset_index(drop=True)
            if predict.empty:
                raise ValueError(f"prediction period has no eligible rows: {period.prediction_start}")
            fit_id = f"rf-small-annual-{policy}-{period.prediction_start:%Y%m%d}"
            model_version = f"rf-small-annual-{policy}-v{period.sequence:03d}"
            preprocessor = preprocessor_type(QUANTITATIVE_BASELINE_FEATURES)
            started = perf_counter()
            train_x = preprocessor.fit_transform(train.loc[:, QUANTITATIVE_BASELINE_FEATURES])
            model = factory()
            model.fit(train_x, train[TARGET_COLUMN].astype(float))
            fit_seconds = perf_counter() - started
            started = perf_counter()
            predict_x = preprocessor.transform(predict.loc[:, QUANTITATIVE_BASELINE_FEATURES])
            predicted_return = np.asarray(model.predict(predict_x), dtype=float)
            prediction_seconds = perf_counter() - started
            result = pd.DataFrame({
                "ticker": predict["ticker"].to_numpy(),
                "decision_date": predict["decision_date"].to_numpy(),
                "actual_return_20d": predict[TARGET_COLUMN].to_numpy(dtype=float),
                "actual_rank_20d": predict[RANK_COLUMN].to_numpy(dtype=float),
                "predicted_return": predicted_return,
            })
            result["predicted_rank"] = cross_sectional_percentile_rank(
                result["predicted_return"], result["decision_date"],
            )
            result["window_policy"] = policy
            result["fit_id"] = fit_id
            result["model_version"] = model_version
            result["training_start"] = train["decision_date"].min()
            result["training_end"] = train["decision_date"].max()
            result["prediction_period_start"] = period.prediction_start
            result["prediction_period_end"] = period.prediction_end
            session_age = {session: index for index, session in enumerate(period.sessions)}
            result["sessions_since_fit"] = result["decision_date"].map(session_age).astype(int)
            result["model_age_bucket"] = result["sessions_since_fit"].map(model_age_bucket)
            result["test_used"] = False
            prediction_frames.append(result)
            preprocessing_metadata = preprocessor.metadata()
            for feature_metadata in preprocessing_metadata["features"]:
                preprocessing_rows.append({
                    "fit_id": fit_id,
                    "window_policy": policy,
                    "fit_partition": preprocessing_metadata["fit_partition"],
                    "preprocessing_version": preprocessing_version,
                    **feature_metadata,
                })
            earliest = train["decision_date"].min()
            latest = train["decision_date"].max()
            fit_row = {
                "fit_id": fit_id,
                "model_family": "rf-small",
                "task": "regression",
                "target": TARGET_COLUMN,
                "frequency": "annual",
                "window_policy": policy,
                "model_version": model_version,
                "nominal_window_start": window_start,
                "effective_training_start": earliest,
                "nominal_training_end": nominal_end,
                "effective_training_end": latest,
                "earliest_training_decision_date": earliest,
                "latest_training_decision_date": latest,
                "max_train_target_end_date": train[TARGET_END_COLUMN].max(),
                "rows_before_purge": int(nominal.sum()),
                "rows_after_purge": int(purged.sum()),
                "purged_rows": int(nominal.sum() - purged.sum()),
                "train_decision_dates": int(train["decision_date"].nunique()),
                "approximate_history_years": float((latest - earliest).days / 365.2425),
                "retrain_date": period.retrain_date,
                "prediction_start": period.prediction_start,
                "prediction_end": period.prediction_end,
                "prediction_sessions": int(predict["decision_date"].nunique()),
                "scheduled_sessions": len(period.sessions),
                "hyperparameters": json.dumps(hyperparameters, sort_keys=True),
                "preprocessing_version": preprocessing_version,
                "feature_count": len(QUANTITATIVE_BASELINE_FEATURES),
                "fit_seconds": fit_seconds,
                "prediction_seconds": prediction_seconds,
                "test_used": False,
            }
            fit_rows.append(fit_row)
            if progress is not None:
                progress(fit_row)
        predictions = pd.concat(prediction_frames, ignore_index=True)
        fits = pd.DataFrame(fit_rows)
        preprocessing = pd.DataFrame(preprocessing_rows)
        return predictions, fits, preprocessing, policy_metrics(predictions, fits)


def training_sample_summary(fits: pd.DataFrame) -> dict[str, float | int]:
    """Summarize how much history a policy retained across annual fits."""
    rows = fits["rows_after_purge"].astype(float)
    years = fits["approximate_history_years"].astype(float)
    return {
        "min_training_rows": int(rows.min()),
        "mean_training_rows": float(rows.mean()),
        "max_training_rows": int(rows.max()),
        "min_training_years": float(years.min()),
        "mean_training_years": float(years.mean()),
        "max_training_years": float(years.max()),
    }
