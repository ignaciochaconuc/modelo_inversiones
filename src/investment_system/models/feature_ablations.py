"""Leave-one-feature-family-out diagnostics for Phase 3D.6."""
from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import numpy as np
import pandas as pd

from investment_system.data.calendar import TradingCalendar
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.metrics import cross_sectional_percentile_rank
from investment_system.models.tree_preprocessing import TreePreprocessor
from investment_system.models.walkforward import (
    RANK_COLUMN,
    SEALED_TEST_START,
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
from investment_system.models.window_sensitivity import window_training_masks

ABLATION_NEUTRAL_TOLERANCE = 0.003
ABLATION_MATERIAL_THRESHOLD = 0.005
REAL_REPRO_TOLERANCE = 1e-12

FEATURE_FAMILIES: dict[str, tuple[str, ...]] = {
    "returns": (
        "return_1d", "return_2d", "return_5d", "return_10d", "return_20d",
        "return_60d", "gap_open", "intraday_return", "overnight_return",
    ),
    "momentum": (
        "momentum_5d", "momentum_10d", "momentum_20d", "momentum_60d",
        "momentum_120d",
    ),
    "relative_momentum": (
        "relative_momentum_spy_5d", "relative_momentum_spy_20d",
        "relative_momentum_spy_60d",
    ),
    "volatility": (
        "volatility_5d", "volatility_10d", "volatility_20d", "volatility_60d",
        "downside_volatility", "atr_pct",
    ),
    "trend": (
        "rsi_14", "macd_pct", "macd_signal_pct", "macd_histogram_pct",
        "distance_ma10", "distance_ma20", "distance_ma50", "distance_ma200",
    ),
    "liquidity_volume": (
        "volume_ratio_5d", "volume_ratio_20d", "volume_change_1d",
        "avg_dollar_volume_20d", "avg_dollar_volume_60d",
    ),
    "drawdown": ("max_drawdown_20d", "max_drawdown_60d"),
    "market": (
        "spy_return_1d", "spy_return_5d", "spy_return_20d",
        "excess_return_5d", "excess_return_20d",
    ),
    "relative_risk": (
        "beta_20d", "beta_60d", "correlation_spy_20d", "correlation_spy_60d",
    ),
    "historical_position": (
        "distance_52w_high", "distance_52w_low", "percentile_price_252d",
        "percentile_volume_252d", "percentile_volatility_252d",
    ),
}

ABLATION_POLICIES: tuple[str, ...] = (
    "full",
    *(f"without_{family}" for family in FEATURE_FAMILIES),
)
EXPECTED_FEATURE_COUNTS = {
    "full": 52,
    **{f"without_{family}": 52 - len(features) for family, features in FEATURE_FAMILIES.items()},
}


def validate_family_contract() -> None:
    """Fail unless ten disjoint families partition the canonical 52 features."""
    if len(FEATURE_FAMILIES) != 10:
        raise ValueError("Phase 3D.6 requires exactly ten feature families")
    flattened = [feature for features in FEATURE_FAMILIES.values() for feature in features]
    if len(flattened) != len(set(flattened)):
        raise ValueError("feature families overlap")
    canonical = tuple(QUANTITATIVE_BASELINE_FEATURES)
    if len(canonical) != 52 or set(flattened) != set(canonical):
        missing = sorted(set(canonical) - set(flattened))
        extra = sorted(set(flattened) - set(canonical))
        raise ValueError(f"feature-family partition mismatch; missing={missing}, extra={extra}")
    if len(ABLATION_POLICIES) != 11:
        raise ValueError("Phase 3D.6 requires exactly eleven policies")


def ablation_policy_features(policy: str) -> tuple[str, ...]:
    """Return the canonical-order subset for a full or leave-one-family-out policy."""
    validate_family_contract()
    if policy == "full":
        return tuple(QUANTITATIVE_BASELINE_FEATURES)
    prefix = "without_"
    if not policy.startswith(prefix) or policy[len(prefix):] not in FEATURE_FAMILIES:
        raise ValueError(f"unsupported ablation policy: {policy}")
    removed = set(FEATURE_FAMILIES[policy[len(prefix):]])
    subset = tuple(feature for feature in QUANTITATIVE_BASELINE_FEATURES if feature not in removed)
    if len(subset) != EXPECTED_FEATURE_COUNTS[policy]:
        raise RuntimeError(f"unexpected feature count for {policy}")
    return subset


def removed_family(policy: str) -> str | None:
    if policy == "full":
        return None
    ablation_policy_features(policy)
    return policy.removeprefix("without_")


def classify_ablation(delta_mean_ic: float) -> str:
    """Classify an arithmetic mean-IC delta using gap-free declared boundaries."""
    if delta_mean_ic <= -ABLATION_MATERIAL_THRESHOLD:
        return "important"
    if delta_mean_ic <= -ABLATION_NEUTRAL_TOLERANCE:
        return "moderately_useful"
    if delta_mean_ic < ABLATION_NEUTRAL_TOLERANCE:
        return "neutral_or_redundant"
    if delta_mean_ic < ABLATION_MATERIAL_THRESHOLD:
        return "small_positive_change"
    return "potentially_harmful"


def diagnostic_flags(
    *, delta_mean_ic: float, delta_worst_year_ic: float,
    delta_icir: float, delta_top10_uplift: float,
) -> dict[str, bool]:
    """Return stability-aware harmful and contribution flags without selecting features."""
    harmful = (
        delta_mean_ic >= ABLATION_MATERIAL_THRESHOLD
        and delta_worst_year_ic >= -ABLATION_NEUTRAL_TOLERANCE
        and delta_icir >= -0.02
        and delta_top10_uplift >= -0.001
    )
    strong = (
        delta_mean_ic <= -ABLATION_MATERIAL_THRESHOLD
        or delta_worst_year_ic <= -ABLATION_MATERIAL_THRESHOLD
    )
    return {"strong_contributor": bool(strong), "harmful_candidate": bool(harmful)}


def policy_deltas(
    policy: str, metrics: dict[str, dict[str, Any]],
) -> dict[str, float]:
    """Calculate simple arithmetic metric deltas against full."""
    base = metrics["full"]
    current = metrics[policy]
    base_rank = base["overall"]["ranking"]["rank_ic"]
    rank = current["overall"]["ranking"]["rank_ic"]
    base_top10 = base["overall"]["ranking"]["top10"]
    top10 = current["overall"]["ranking"]["top10"]
    return {
        "delta_mean_ic_vs_full": float(rank["mean"] - base_rank["mean"]),
        "delta_icir_vs_full": float(rank["icir"] - base_rank["icir"]),
        "delta_pct_positive_ic_vs_full": float(
            rank["pct_positive"] - base_rank["pct_positive"]
        ),
        "delta_worst_year_ic_vs_full": float(
            current["stability"]["worst_year_ic"] - base["stability"]["worst_year_ic"]
        ),
        "delta_year_ic_std_vs_full": float(
            current["stability"]["year_ic_std"] - base["stability"]["year_ic_std"]
        ),
        "delta_top10_uplift_vs_full": float(
            top10["average_top10_uplift"] - base_top10["average_top10_uplift"]
        ),
    }


class Phase3DFeatureAblationRunner:
    """Run frozen annual expanding RF-Small on one declared feature subset."""

    def __init__(self, output_root: str | Path, calendar: TradingCalendar) -> None:
        validate_family_contract()
        self.output_root = Path(output_root)
        self.calendar = calendar

    def run_policy(
        self, frame: pd.DataFrame, policy: str, *,
        progress: Callable[[dict[str, Any]], None] | None = None,
    ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, Any]]:
        features = ablation_policy_features(policy)
        family = removed_family(policy)
        if (
            (frame["decision_date"] >= SEALED_TEST_START).any()
            or (frame[TARGET_END_COLUMN] >= SEALED_TEST_START).any()
        ):
            raise ValueError("Phase 3D.6 runner must not receive TEST rows or TEST-reaching labels")
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
            nominal, purged, _, nominal_end = window_training_masks(
                frame, period.prediction_start, "expanding",
            )
            train = frame.loc[purged].reset_index(drop=True)
            predict = frame.loc[frame["decision_date"].isin(period.sessions)].reset_index(drop=True)
            if predict.empty:
                raise ValueError(f"prediction period has no eligible rows: {period.prediction_start}")
            fit_id = f"rf-small-annual-expanding-{policy}-{period.prediction_start:%Y%m%d}"
            model_version = f"rf-small-annual-expanding-{policy}-v{period.sequence:03d}"
            preprocessor = preprocessor_type(features)
            started = perf_counter()
            train_x = preprocessor.fit_transform(train.loc[:, features])
            model = factory()
            model.fit(train_x, train[TARGET_COLUMN].astype(float))
            fit_seconds = perf_counter() - started
            started = perf_counter()
            predict_x = preprocessor.transform(predict.loc[:, features])
            predicted_return = np.asarray(model.predict(predict_x), dtype=float)
            prediction_seconds = perf_counter() - started
            effective_count = len(preprocessor.effective_feature_names)
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
            result["ablation_policy"] = policy
            result["removed_family"] = family
            result["feature_count_requested"] = len(features)
            result["feature_count_effective"] = effective_count
            result["fit_id"] = fit_id
            result["model_version"] = model_version
            result["fit_training_start"] = train["decision_date"].min()
            result["fit_training_end"] = train["decision_date"].max()
            result["prediction_period_start"] = period.prediction_start
            result["prediction_period_end"] = period.prediction_end
            session_age = {session: index for index, session in enumerate(period.sessions)}
            result["sessions_since_fit"] = result["decision_date"].map(session_age).astype(int)
            result["model_age_bucket"] = result["sessions_since_fit"].map(model_age_bucket)
            result["test_used"] = False
            prediction_frames.append(result)
            metadata = preprocessor.metadata()
            for feature_metadata in metadata["features"]:
                preprocessing_rows.append({
                    "fit_id": fit_id,
                    "ablation_policy": policy,
                    "removed_family": family,
                    "fit_partition": metadata["fit_partition"],
                    "preprocessing_version": preprocessing_version,
                    **feature_metadata,
                })
            fit_row = {
                "fit_id": fit_id,
                "ablation_policy": policy,
                "removed_family": family,
                "model_family": "rf-small",
                "task": "regression",
                "target": TARGET_COLUMN,
                "frequency": "annual",
                "window_policy": "expanding",
                "model_version": model_version,
                "feature_count_requested": len(features),
                "feature_count_effective": effective_count,
                "excluded_zero_variance_features": json.dumps(
                    list(preprocessor.excluded_degenerate_features)
                ),
                "training_start": train["decision_date"].min(),
                "nominal_training_end": nominal_end,
                "effective_training_end": train["decision_date"].max(),
                "max_train_target_end_date": train[TARGET_END_COLUMN].max(),
                "rows_before_purge": int(nominal.sum()),
                "rows_after_purge": int(purged.sum()),
                "purged_rows": int(nominal.sum() - purged.sum()),
                "train_decision_dates": int(train["decision_date"].nunique()),
                "retrain_date": period.retrain_date,
                "prediction_start": period.prediction_start,
                "prediction_end": period.prediction_end,
                "prediction_sessions": int(predict["decision_date"].nunique()),
                "scheduled_sessions": len(period.sessions),
                "hyperparameters": json.dumps(hyperparameters, sort_keys=True),
                "preprocessing_version": preprocessing_version,
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


validate_family_contract()
