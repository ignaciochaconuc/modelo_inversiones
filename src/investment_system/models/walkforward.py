"""Causal expanding-window infrastructure for Phase 3D robustness analysis."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable, Iterable, Literal, Sequence

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import Ridge

from investment_system.core.reproducibility import git_metadata
from investment_system.data.calendar import TradingCalendar
from investment_system.features.targets import TARGET_COLUMNS, TARGET_METADATA_COLUMNS
from investment_system.models.feature_sets import (
    QUANTITATIVE_BASELINE_FEATURES,
    QUANTITATIVE_BASELINE_VERSION,
)
from investment_system.models.metrics import (
    cross_sectional_percentile_rank,
    ranking_metrics,
    regression_metrics,
)
from investment_system.models.nonlinear_profiles import RANDOM_STATE, TREE_PROFILES
from investment_system.models.preprocessing import BaselinePreprocessor, PREPROCESSING_VERSION
from investment_system.models.tree_preprocessing import TREE_PREPROCESSING_VERSION, TreePreprocessor

INITIAL_TRAIN_START = date(2010, 1, 4)
INITIAL_TRAIN_END = date(2015, 12, 31)
WALKFORWARD_START = date(2016, 1, 1)
WALKFORWARD_END = date(2021, 12, 31)
SEALED_TEST_START = date(2022, 1, 3)
TARGET_COLUMN = "target_return_20d"
RANK_COLUMN = "target_rank_20d"
TARGET_END_COLUMN = "target_end_date_20d"
ELIGIBILITY_COLUMN = "target_20d_training_eligible"
RETRAIN_IC_TOLERANCE = 0.003
FREQUENCIES = ("monthly", "quarterly", "semiannual", "annual")
FREQUENCY_COST_ORDER = {"annual": 0, "semiannual": 1, "quarterly": 2, "monthly": 3}
MODEL_AGE_BUCKETS = ("0-20", "21-40", "41-60", "61-120", "121+")
WALKFORWARD_PURGE_RULE_VERSION = "dynamic-target-end-date-strict-v1"


@dataclass(frozen=True)
class WalkForwardPeriod:
    frequency: str
    sequence: int
    retrain_date: date
    prediction_start: date
    prediction_end: date
    sessions: tuple[date, ...]


@dataclass(frozen=True)
class FrequencySelection:
    model_family: str
    raw_best_frequency: str
    selected_frequency: str
    best_mean_ic: float
    selected_mean_ic: float
    delta_vs_best_ic: float
    retrain_count: int
    rationale: str


def xnys_sessions(calendar: TradingCalendar, start: date, end: date) -> tuple[date, ...]:
    """Return inclusive exchange sessions without relying on calendar-day offsets."""
    if end < start:
        raise ValueError("session range end precedes start")
    current = start if calendar.is_session(start) else calendar.next_session(start)
    sessions: list[date] = []
    while current <= end:
        sessions.append(current)
        current = calendar.next_session(current)
    return tuple(sessions)


def _frequency_key(value: date, frequency: str) -> tuple[int, int]:
    if frequency == "monthly":
        return value.year, value.month
    if frequency == "quarterly":
        return value.year, (value.month - 1) // 3
    if frequency == "semiannual":
        return value.year, (value.month - 1) // 6
    if frequency == "annual":
        return value.year, 0
    raise ValueError(f"unsupported retraining frequency: {frequency}")


def build_walkforward_schedule(
    calendar: TradingCalendar,
    frequency: str,
    *,
    start: date = WALKFORWARD_START,
    end: date = WALKFORWARD_END,
) -> tuple[WalkForwardPeriod, ...]:
    """Group consecutive XNYS sessions into deterministic activation periods."""
    sessions = xnys_sessions(calendar, start, end)
    if not sessions:
        raise ValueError("walk-forward schedule contains no XNYS sessions")
    groups: list[list[date]] = []
    for session in sessions:
        if not groups or _frequency_key(groups[-1][0], frequency) != _frequency_key(session, frequency):
            groups.append([])
        groups[-1].append(session)
    return tuple(
        WalkForwardPeriod(
            frequency=frequency,
            sequence=index,
            retrain_date=group[0],
            prediction_start=group[0],
            prediction_end=group[-1],
            sessions=tuple(group),
        )
        for index, group in enumerate(groups, start=1)
    )


def validate_schedule(periods: Sequence[WalkForwardPeriod], expected_sessions: Sequence[date]) -> None:
    """Fail on overlaps, gaps, duplicated sessions, or inconsistent boundaries."""
    flattened = [session for period in periods for session in period.sessions]
    if flattened != list(expected_sessions):
        raise ValueError("walk-forward periods are not contiguous over expected XNYS sessions")
    if len(flattened) != len(set(flattened)):
        raise ValueError("walk-forward schedule contains overlapping sessions")
    for period in periods:
        if not period.sessions or period.sessions[0] != period.prediction_start:
            raise ValueError("period start differs from its first session")
        if period.sessions[-1] != period.prediction_end:
            raise ValueError("period end differs from its last session")


def model_age_bucket(value: int) -> str:
    if value < 0:
        raise ValueError("sessions_since_fit cannot be negative")
    if value <= 20:
        return "0-20"
    if value <= 40:
        return "21-40"
    if value <= 60:
        return "41-60"
    if value <= 120:
        return "61-120"
    return "121+"


def build_walkforward_frame(features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    """Join separate stores into a label-safe 20d robustness frame."""
    keys = ["ticker", "decision_date"]
    for name, frame in (("features", features), ("targets", targets)):
        if frame.duplicated(keys).any():
            raise ValueError(f"duplicate ticker + decision_date in {name}")
    if tuple(column for column in QUANTITATIVE_BASELINE_FEATURES if column in features) != QUANTITATIVE_BASELINE_FEATURES:
        raise ValueError("walk-forward requires the exact quantitative-baseline-v1 feature allowlist")
    forbidden = (set(TARGET_COLUMNS) | set(TARGET_METADATA_COLUMNS)) & set(QUANTITATIVE_BASELINE_FEATURES)
    if forbidden:
        raise ValueError(f"target columns cannot enter X: {sorted(forbidden)}")
    feature_columns = [
        *keys, "model_eligible", "feature_corporate_action_contaminated",
        *QUANTITATIVE_BASELINE_FEATURES,
    ]
    target_columns = [*keys, TARGET_COLUMN, RANK_COLUMN, TARGET_END_COLUMN, ELIGIBILITY_COLUMN]
    joined = features[feature_columns].merge(
        targets[target_columns], on=keys, how="inner", validate="one_to_one",
    )
    joined["decision_date"] = pd.to_datetime(joined["decision_date"]).dt.date
    joined[TARGET_END_COLUMN] = pd.to_datetime(joined[TARGET_END_COLUMN]).dt.date
    boolean = lambda values: values.astype("boolean").fillna(False).astype(bool)
    eligible = (
        boolean(joined["model_eligible"])
        & ~boolean(joined["feature_corporate_action_contaminated"])
        & boolean(joined[ELIGIBILITY_COLUMN])
        & joined[TARGET_COLUMN].notna()
        & joined[RANK_COLUMN].notna()
        & joined[TARGET_END_COLUMN].notna()
    )
    date_mask = joined["decision_date"].between(INITIAL_TRAIN_START, WALKFORWARD_END)
    label_safe = joined[TARGET_END_COLUMN] < SEALED_TEST_START
    result = joined.loc[eligible & date_mask & label_safe, [
        *keys, *QUANTITATIVE_BASELINE_FEATURES, TARGET_COLUMN, RANK_COLUMN, TARGET_END_COLUMN,
    ]].sort_values(keys[::-1], kind="mergesort").reset_index(drop=True)
    if result.empty:
        raise ValueError("walk-forward frame is empty")
    if result[TARGET_END_COLUMN].max() >= SEALED_TEST_START:
        raise ValueError("walk-forward frame contains a label crossing into TEST")
    return result


def dynamic_training_masks(
    frame: pd.DataFrame, prediction_start: date,
) -> tuple[pd.Series, pd.Series, date]:
    """Return nominal and strictly purged expanding-window masks."""
    nominal_end = max(value for value in frame["decision_date"].unique() if value < prediction_start)
    nominal = frame["decision_date"].between(INITIAL_TRAIN_START, nominal_end)
    purged = nominal & (frame[TARGET_END_COLUMN] < prediction_start)
    if not purged.any():
        raise ValueError(f"dynamic purge leaves no training rows for {prediction_start}")
    if frame.loc[purged, TARGET_END_COLUMN].max() >= prediction_start:
        raise ValueError("dynamic purge invariant failed")
    return nominal, purged, nominal_end


def _age_metrics(predictions: pd.DataFrame) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for bucket in MODEL_AGE_BUCKETS:
        subset = predictions.loc[predictions["model_age_bucket"].eq(bucket)].reset_index(drop=True)
        if subset.empty:
            result[bucket] = {
                "rows": 0, "decision_dates": 0, "rank_ic": None, "top10": None,
            }
            continue
        ranking = ranking_metrics(
            subset["actual_rank_20d"], subset["actual_return_20d"],
            subset["predicted_return"], subset["decision_date"],
        )
        result[bucket] = {
            "rows": int(len(subset)),
            "decision_dates": int(subset["decision_date"].nunique()),
            "rank_ic": ranking["rank_ic"],
            "top10": ranking["top10"],
        }
    return result


def policy_metrics(predictions: pd.DataFrame, fits: pd.DataFrame) -> dict[str, Any]:
    """Compute regression, ranking, annual stability, age, and operational cost."""
    regression = regression_metrics(
        predictions["actual_return_20d"], predictions["predicted_return"],
        predictions["decision_date"],
    )
    ranking = ranking_metrics(
        predictions["actual_rank_20d"], predictions["actual_return_20d"],
        predictions["predicted_return"], predictions["decision_date"],
    )
    years = pd.to_datetime(predictions["decision_date"]).dt.year
    by_year: dict[str, Any] = {}
    yearly_ic: list[float] = []
    for year in range(2016, 2022):
        subset = predictions.loc[years.eq(year)].reset_index(drop=True)
        annual = ranking_metrics(
            subset["actual_rank_20d"], subset["actual_return_20d"],
            subset["predicted_return"], subset["decision_date"],
        )
        by_year[str(year)] = annual
        value = annual["rank_ic"]["mean"]
        if value is not None:
            yearly_ic.append(float(value))
    fit_seconds = fits["fit_seconds"].astype(float)
    stability = {
        "worst_year_ic": min(yearly_ic),
        "best_year_ic": max(yearly_ic),
        "year_ic_std": float(np.std(yearly_ic, ddof=1)),
        "positive_years": int(sum(value > 0 for value in yearly_ic)),
        "negative_years": int(sum(value < 0 for value in yearly_ic)),
    }
    cost = {
        "number_of_retrains": int(len(fits)),
        "total_fit_seconds": float(fit_seconds.sum()),
        "mean_fit_seconds": float(fit_seconds.mean()),
        "median_fit_seconds": float(fit_seconds.median()),
        "max_fit_seconds": float(fit_seconds.max()),
        "total_prediction_seconds": float(fits["prediction_seconds"].sum()),
    }
    return {
        "overall": {"regression": regression, "ranking": ranking},
        "by_year": by_year,
        "stability": stability,
        "operational_cost": cost,
        "model_age": _age_metrics(predictions),
    }


def select_operational_frequency(model_family: str, policy_results: dict[str, dict[str, Any]]) -> FrequencySelection:
    """Prefer the cheapest frequency within 0.003 of the best walk-forward IC."""
    def mean_ic(frequency: str) -> float:
        return float(policy_results[frequency]["overall"]["ranking"]["rank_ic"]["mean"])
    raw_best = max(FREQUENCIES, key=lambda frequency: (mean_ic(frequency), -FREQUENCY_COST_ORDER[frequency]))
    best_ic = mean_ic(raw_best)
    equivalent = [frequency for frequency in FREQUENCIES if mean_ic(frequency) >= best_ic - RETRAIN_IC_TOLERANCE]
    minimum_cost = min(
        policy_results[frequency]["operational_cost"]["number_of_retrains"]
        for frequency in equivalent
    )
    cheapest = [
        frequency for frequency in equivalent
        if policy_results[frequency]["operational_cost"]["number_of_retrains"] == minimum_cost
    ]
    selected = max(cheapest, key=lambda frequency: (
        policy_results[frequency]["stability"]["worst_year_ic"],
        policy_results[frequency]["overall"]["ranking"]["rank_ic"]["icir"],
        policy_results[frequency]["overall"]["ranking"]["rank_ic"]["pct_positive"],
        policy_results[frequency]["overall"]["ranking"]["top10"]["average_top10_uplift"],
        -FREQUENCY_COST_ORDER[frequency],
    ))
    selected_ic = mean_ic(selected)
    return FrequencySelection(
        model_family=model_family,
        raw_best_frequency=raw_best,
        selected_frequency=selected,
        best_mean_ic=best_ic,
        selected_mean_ic=selected_ic,
        delta_vs_best_ic=selected_ic - best_ic,
        retrain_count=int(policy_results[selected]["operational_cost"]["number_of_retrains"]),
        rationale=(
            f"{selected} has the fewest retrainings among frequencies within "
            f"{RETRAIN_IC_TOLERANCE:.3f} of raw-best {raw_best}; secondary order is "
            "worst-year IC, ICIR, positive-IC share, then top10 uplift"
        ),
    )


class Phase3DWalkForwardRunner:
    """Fit only frozen RF-Small and Ridge-100 on causal expanding windows."""

    def __init__(
        self, output_root: str | Path, calendar: TradingCalendar, *,
        feature_schema_version: str, target_schema_version: str,
        mode: str = "robustness-selection",
    ) -> None:
        if mode != "robustness-selection":
            raise ValueError("Phase 3D only supports mode='robustness-selection'")
        self.output_root = Path(output_root)
        self.calendar = calendar
        self.feature_schema_version = feature_schema_version
        self.target_schema_version = target_schema_version
        self.mode = mode

    @staticmethod
    def _model_factory(model_family: str) -> tuple[Callable[[], Any], type[Any], str, dict[str, Any]]:
        if model_family == "rf-small":
            profile = next(item for item in TREE_PROFILES if item.family == "rf" and item.name == "small")
            return profile.regressor, TreePreprocessor, TREE_PREPROCESSING_VERSION, dict(profile.parameters)
        if model_family == "ridge-100":
            return lambda: Ridge(alpha=100.0), BaselinePreprocessor, PREPROCESSING_VERSION, {"alpha": 100.0}
        raise ValueError(f"unsupported frozen model: {model_family}")

    def run_policy(
        self, frame: pd.DataFrame, model_family: str, frequency: str,
        *, progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        factory, preprocessor_type, preprocessing_version, hyperparameters = self._model_factory(model_family)
        safe_end = min(WALKFORWARD_END, max(frame.loc[
            frame["decision_date"].between(WALKFORWARD_START, WALKFORWARD_END), "decision_date"
        ]))
        periods = build_walkforward_schedule(self.calendar, frequency, start=WALKFORWARD_START, end=safe_end)
        expected_sessions = xnys_sessions(self.calendar, WALKFORWARD_START, safe_end)
        validate_schedule(periods, expected_sessions)
        prediction_frames: list[pd.DataFrame] = []
        fit_rows: list[dict[str, Any]] = []
        preprocessing_rows: list[dict[str, Any]] = []
        for period in periods:
            nominal, purged, nominal_end = dynamic_training_masks(frame, period.prediction_start)
            prediction_mask = frame["decision_date"].isin(period.sessions)
            train = frame.loc[purged].reset_index(drop=True)
            predict = frame.loc[prediction_mask].reset_index(drop=True)
            if predict.empty:
                raise ValueError(f"prediction period has no eligible rows: {period.prediction_start}")
            fit_id = f"{model_family}-{frequency}-{period.prediction_start:%Y%m%d}"
            model_version = f"{model_family}-{frequency}-v{period.sequence:03d}"
            preprocessor = preprocessor_type(QUANTITATIVE_BASELINE_FEATURES)
            fit_started = perf_counter()
            train_x = preprocessor.fit_transform(train.loc[:, QUANTITATIVE_BASELINE_FEATURES])
            model = factory()
            model.fit(train_x, train[TARGET_COLUMN].astype(float))
            fit_seconds = perf_counter() - fit_started
            prediction_started = perf_counter()
            predict_x = preprocessor.transform(predict.loc[:, QUANTITATIVE_BASELINE_FEATURES])
            predicted_return = np.asarray(model.predict(predict_x), dtype=float)
            prediction_seconds = perf_counter() - prediction_started
            result = pd.DataFrame({
                "ticker": predict["ticker"].to_numpy(),
                "decision_date": predict["decision_date"].to_numpy(),
                "actual_return_20d": predict[TARGET_COLUMN].to_numpy(dtype=float),
                "actual_rank_20d": predict[RANK_COLUMN].to_numpy(dtype=float),
                "predicted_return": predicted_return,
            })
            result["predicted_rank"] = cross_sectional_percentile_rank(
                result["predicted_return"], result["decision_date"]
            )
            session_age = {session: index for index, session in enumerate(period.sessions)}
            result["model_family"] = model_family
            result["retraining_frequency"] = frequency
            result["model_version"] = model_version
            result["fit_id"] = fit_id
            result["fit_training_start"] = INITIAL_TRAIN_START
            result["fit_training_end"] = train["decision_date"].max()
            result["prediction_period_start"] = period.prediction_start
            result["prediction_period_end"] = period.prediction_end
            result["sessions_since_fit"] = result["decision_date"].map(session_age).astype(int)
            result["model_age_bucket"] = result["sessions_since_fit"].map(model_age_bucket)
            result["test_used"] = False
            prediction_frames.append(result)
            metadata = preprocessor.metadata()
            for row in metadata["features"]:
                preprocessing_rows.append({"fit_id": fit_id, **row})
            fit_row = {
                "fit_id": fit_id, "model_family": model_family, "frequency": frequency,
                "model_version": model_version, "training_start": INITIAL_TRAIN_START,
                "nominal_training_end": nominal_end,
                "effective_training_end": train["decision_date"].max(),
                "max_train_target_end_date": train[TARGET_END_COLUMN].max(),
                "rows_before_purge": int(nominal.sum()), "rows_after_purge": int(purged.sum()),
                "purged_rows": int(nominal.sum() - purged.sum()),
                "train_decision_dates": int(train["decision_date"].nunique()),
                "retrain_date": period.retrain_date,
                "prediction_start": period.prediction_start, "prediction_end": period.prediction_end,
                "prediction_sessions": int(predict["decision_date"].nunique()),
                "scheduled_sessions": len(period.sessions),
                "hyperparameters": json.dumps(hyperparameters, sort_keys=True),
                "preprocessing_version": preprocessing_version,
                "fit_seconds": fit_seconds, "prediction_seconds": prediction_seconds,
                "test_used": False,
            }
            fit_rows.append(fit_row)
            if progress is not None:
                progress(fit_row)
        predictions = pd.concat(prediction_frames, ignore_index=True)
        fits = pd.DataFrame(fit_rows)
        preprocessing = pd.DataFrame(preprocessing_rows)
        metrics = policy_metrics(predictions, fits)
        return predictions, fits, preprocessing, metrics

    def global_manifest(self, *, effective_prediction_end: date) -> dict[str, Any]:
        return {
            "phase": "3D-walk-forward-robustness", "scope": "3D.1-3D.4",
            "mode": self.mode, "feature_set_version": QUANTITATIVE_BASELINE_VERSION,
            "rf_preprocessing_version": TREE_PREPROCESSING_VERSION,
            "ridge_preprocessing_version": PREPROCESSING_VERSION,
            "target": TARGET_COLUMN, "ranking_target": RANK_COLUMN, "horizon": 20,
            "initial_training_dates": [str(INITIAL_TRAIN_START), str(INITIAL_TRAIN_END)],
            "walk_forward_dates": [str(WALKFORWARD_START), str(WALKFORWARD_END)],
            "effective_label_safe_prediction_end": str(effective_prediction_end),
            "frequencies": list(FREQUENCIES), "window_type": "expanding",
            "purge_rule": f"{TARGET_END_COLUMN} < prediction_period_start",
            "purge_rule_version": WALKFORWARD_PURGE_RULE_VERSION,
            "retrain_ic_tolerance": RETRAIN_IC_TOLERANCE,
            "feature_schema_version": self.feature_schema_version,
            "target_schema_version": self.target_schema_version,
            "sklearn_version": sklearn.__version__, "random_state": RANDOM_STATE,
            "generated_at": datetime.now(timezone.utc).isoformat(), **git_metadata(),
            "test_used": False,
        }


def compact_policy_row(model: str, frequency: str, metrics: dict[str, Any]) -> dict[str, Any]:
    rank = metrics["overall"]["ranking"]["rank_ic"]
    regression = metrics["overall"]["regression"]["pooled"]
    top10 = metrics["overall"]["ranking"]["top10"]
    return {
        "model_family": model, "frequency": frequency,
        "mean_ic": rank["mean"], "median_ic": rank["median"], "std_ic": rank["std"],
        "icir": rank["icir"], "pct_positive_ic": rank["pct_positive"],
        "mae": regression["mae"], "rmse": regression["rmse"],
        "pooled_pearson": regression["pearson_correlation"],
        "pooled_spearman": regression["spearman_correlation"],
        "top10_uplift": top10["average_top10_uplift"],
        "pct_dates_positive_uplift": top10["pct_dates_positive_uplift"],
        **metrics["stability"], **metrics["operational_cost"], "test_used": False,
    }


def compare_models(
    rf_frequency: str, ridge_frequency: str,
    all_metrics: dict[str, dict[str, dict[str, Any]]],
) -> dict[str, Any]:
    rf = all_metrics["rf-small"][rf_frequency]
    ridge = all_metrics["ridge-100"][ridge_frequency]
    rf_rank = rf["overall"]["ranking"]
    ridge_rank = ridge["overall"]["ranking"]
    return {
        "rf_frequency": rf_frequency, "ridge_frequency": ridge_frequency,
        "rf_mean_ic": rf_rank["rank_ic"]["mean"], "ridge_mean_ic": ridge_rank["rank_ic"]["mean"],
        "delta_mean_ic": rf_rank["rank_ic"]["mean"] - ridge_rank["rank_ic"]["mean"],
        "rf_icir": rf_rank["rank_ic"]["icir"], "ridge_icir": ridge_rank["rank_ic"]["icir"],
        "delta_icir": rf_rank["rank_ic"]["icir"] - ridge_rank["rank_ic"]["icir"],
        "rf_worst_year_ic": rf["stability"]["worst_year_ic"],
        "ridge_worst_year_ic": ridge["stability"]["worst_year_ic"],
        "delta_worst_year_ic": rf["stability"]["worst_year_ic"] - ridge["stability"]["worst_year_ic"],
        "rf_pct_positive_ic": rf_rank["rank_ic"]["pct_positive"],
        "ridge_pct_positive_ic": ridge_rank["rank_ic"]["pct_positive"],
        "rf_top10_uplift": rf_rank["top10"]["average_top10_uplift"],
        "ridge_top10_uplift": ridge_rank["top10"]["average_top10_uplift"],
        "delta_top10_uplift": rf_rank["top10"]["average_top10_uplift"] - ridge_rank["top10"]["average_top10_uplift"],
        "rf_positive_years": rf["stability"]["positive_years"],
        "ridge_positive_years": ridge["stability"]["positive_years"],
        "rf_retrain_count": rf["operational_cost"]["number_of_retrains"],
        "ridge_retrain_count": ridge["operational_cost"]["number_of_retrains"],
        "rf_total_fit_seconds": rf["operational_cost"]["total_fit_seconds"],
        "ridge_total_fit_seconds": ridge["operational_cost"]["total_fit_seconds"],
    }
