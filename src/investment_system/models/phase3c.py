"""Phase 3C nonlinear model selection with a physically sealed TEST partition."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Iterable, Sequence

import lightgbm
import numpy as np
import pandas as pd
import sklearn
import xgboost
from sklearn.inspection import permutation_importance

from investment_system.core.reproducibility import git_metadata
from investment_system.models.contracts import TargetSpec
from investment_system.models.feature_sets import (
    QUANTITATIVE_BASELINE_FEATURES,
    QUANTITATIVE_BASELINE_VERSION,
)
from investment_system.models.metrics import (
    classification_metrics,
    cross_sectional_percentile_rank,
    daily_correlations,
    ranking_metrics,
    regression_metrics,
)
from investment_system.models.nonlinear_profiles import RANDOM_STATE, TREE_PROFILES, TreeProfile
from investment_system.models.phase3b import SelectionDataset
from investment_system.models.tree_preprocessing import TREE_PREPROCESSING_VERSION, TreePreprocessor

IC_TOLERANCE = 0.001
AUC_TOLERANCE = 0.001
VALIDATION_YEARS = (2019, 2020, 2021)
PERMUTATION_REPEATS = 2


@dataclass
class NonlinearResult:
    experiment_id: str
    family: str
    profile: str
    complexity: int
    task: str
    approach: str
    horizon: int
    metrics: dict[str, Any]
    manifest: dict[str, Any]
    predictions: pd.DataFrame
    preprocessing: dict[str, Any]
    is_fit: bool
    model: Any | None = None
    preprocessor: TreePreprocessor | None = None
    validation_x: pd.DataFrame | None = None
    validation_y: pd.Series | None = None
    validation_metadata: pd.DataFrame | None = None


def experiment_id(profile: TreeProfile, task: str, horizon: int, approach: str = "model") -> str:
    task_slug = task if approach == "model" else f"{approach}-{task}"
    return (
        f"{profile.profile_id}-{task_slug}-{horizon}d-"
        "qbaselinev1-treeprepv1"
    )


def _finite(value: Any, default: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if np.isfinite(number) else default


def _metric(result: NonlinearResult, *path: str, default: float) -> float:
    value: Any = result.metrics
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return _finite(value, default)


def _primary(result: NonlinearResult) -> float:
    if result.task == "classification":
        return _metric(result, "overall", "roc_auc", default=-np.inf)
    branch = "daily_spearman" if result.task == "regression" else "rank_ic"
    return _metric(result, "overall", branch, "mean", default=-np.inf)


def _selection_key(result: NonlinearResult) -> tuple[Any, ...]:
    if result.task == "classification":
        return (
            -_metric(result, "overall", "log_loss", default=np.inf),
            _metric(result, "overall", "balanced_accuracy", default=-np.inf),
            _metric(result, "stability", "worst_year_auc", default=-np.inf),
            -result.complexity,
            result.experiment_id,
        )
    branch = "daily_spearman" if result.task == "regression" else "rank_ic"
    return (
        _metric(result, "overall", branch, "icir", default=-np.inf),
        _metric(result, "overall", branch, "pct_positive", default=-np.inf),
        _metric(result, "stability", "worst_year_ic", default=-np.inf),
        -result.complexity,
        result.experiment_id,
    )


def select_candidate(candidates: Sequence[NonlinearResult]) -> NonlinearResult:
    """Apply the frozen tolerance, secondary metrics, stability, and complexity."""
    if not candidates:
        raise ValueError("cannot select from an empty candidate list")
    tasks = {item.task for item in candidates}
    horizons = {item.horizon for item in candidates}
    if len(tasks) != 1 or len(horizons) != 1:
        raise ValueError("selection candidates must share task and horizon")
    tolerance = AUC_TOLERANCE if candidates[0].task == "classification" else IC_TOLERANCE
    best = max(_primary(item) for item in candidates)
    close = [item for item in candidates if _primary(item) >= best - tolerance]
    return max(close, key=_selection_key)


def stability_metrics(metrics: dict[str, Any], task: str) -> dict[str, float | None]:
    """Expose explicit 2019/2020/2021 and worst-year stability diagnostics."""
    values: list[float] = []
    output: dict[str, float | None] = {}
    for year in VALIDATION_YEARS:
        year_metrics = metrics["by_year"].get(str(year), {})
        if task == "classification":
            value = year_metrics.get("roc_auc")
            output[f"auc_{year}"] = value
        else:
            branch = "daily_spearman" if task == "regression" else "rank_ic"
            value = year_metrics.get(branch, {}).get("mean")
            output[f"ic_{year}"] = value
        if value is not None and np.isfinite(value):
            values.append(float(value))
    suffix = "auc" if task == "classification" else "ic"
    output[f"worst_year_{suffix}"] = min(values) if values else None
    output[f"year_{suffix}_std"] = float(np.std(values, ddof=1)) if len(values) > 1 else None
    return output


def improvement_flags(task: str, comparison: dict[str, Any]) -> dict[str, bool]:
    """Interpret improvement without using it as a model-selection filter."""
    if task == "classification":
        delta = _finite(comparison.get("delta_auc"), -np.inf)
        stable_delta = _finite(comparison.get("delta_worst_year_auc"), -np.inf)
    else:
        delta = _finite(comparison.get("delta_mean_ic"), -np.inf)
        stable_delta = _finite(comparison.get("delta_worst_year_ic"), -np.inf)
    return {
        "numerical_improvement": delta > 0,
        "material_improvement": delta >= 0.005,
        "stability_improvement": stable_delta > 0,
    }


def _by_year_regression(actual: pd.Series, prediction: np.ndarray, metadata: pd.DataFrame) -> dict[str, Any]:
    years = pd.to_datetime(metadata["decision_date"]).dt.year
    return {
        str(year): regression_metrics(
            actual.loc[years.eq(year).to_numpy()].reset_index(drop=True),
            prediction[years.eq(year).to_numpy()],
            metadata.loc[years.eq(year).to_numpy(), "decision_date"].reset_index(drop=True),
        )
        for year in VALIDATION_YEARS
    }


def _regression_bundle(actual: pd.Series, prediction: np.ndarray, metadata: pd.DataFrame) -> dict[str, Any]:
    result = {
        "overall": regression_metrics(actual, prediction, metadata["decision_date"]),
        "by_year": _by_year_regression(actual, prediction, metadata),
        "primary_selection_metric": "mean_daily_cross_sectional_spearman_ic",
        "selection_tolerance": IC_TOLERANCE,
        "tie_breaking": ["icir", "pct_days_ic_positive", "worst_year_ic", "lower_complexity"],
    }
    result["stability"] = stability_metrics(result, "regression")
    return result


def _classification_bundle(
    train_actual: pd.Series, actual: pd.Series, probability: np.ndarray, metadata: pd.DataFrame
) -> dict[str, Any]:
    years = pd.to_datetime(metadata["decision_date"]).dt.year
    result = {
        "overall": classification_metrics(actual, probability),
        "by_year": {
            str(year): classification_metrics(
                actual.loc[years.eq(year).to_numpy()].reset_index(drop=True),
                probability[years.eq(year).to_numpy()],
            ) for year in VALIDATION_YEARS
        },
        "train_positive_prevalence": float(train_actual.astype(float).mean()),
        "validation_positive_prevalence": float(actual.astype(float).mean()),
        "primary_selection_metric": "roc_auc",
        "selection_tolerance": AUC_TOLERANCE,
        "tie_breaking": ["log_loss", "balanced_accuracy", "worst_year_auc", "lower_complexity"],
        "classification_threshold": 0.5,
    }
    result["stability"] = stability_metrics(result, "classification")
    return result


def _ranking_bundle(
    actual_rank: pd.Series, actual_return: pd.Series, score: np.ndarray, metadata: pd.DataFrame
) -> dict[str, Any]:
    years = pd.to_datetime(metadata["decision_date"]).dt.year
    def evaluate(mask: np.ndarray) -> dict[str, Any]:
        return ranking_metrics(
            actual_rank.loc[mask].reset_index(drop=True),
            actual_return.loc[mask].reset_index(drop=True), score[mask],
            metadata.loc[mask, "decision_date"].reset_index(drop=True),
        )
    result = {
        "overall": evaluate(np.ones(len(actual_rank), dtype=bool)),
        "by_year": {str(year): evaluate(years.eq(year).to_numpy()) for year in VALIDATION_YEARS},
        "primary_selection_metric": "mean_daily_cross_sectional_spearman_rank_ic",
        "selection_tolerance": IC_TOLERANCE,
        "tie_breaking": ["icir", "pct_days_ic_positive", "worst_year_ic", "lower_complexity"],
    }
    result["stability"] = stability_metrics(result, "ranking")
    return result


class _RankICScorer:
    """Pickleable validation scorer for permutation importance."""

    def __init__(self, dates: pd.Series) -> None:
        self.dates = pd.Series(dates).reset_index(drop=True)

    def __call__(self, estimator: Any, x: pd.DataFrame, y: pd.Series) -> float:
        daily = daily_correlations(
            pd.Series(np.asarray(y, dtype=float)),
            pd.Series(np.asarray(estimator.predict(x), dtype=float)),
            self.dates.iloc[:len(y)], method="spearman",
        )
        return float(daily.mean())


class Phase3CSelectionRunner:
    """Run frozen nonlinear profiles; its public data contract contains no TEST."""

    def __init__(
        self, output_root: str | Path, *, feature_schema_version: str,
        target_schema_version: str, mode: str = "selection",
    ) -> None:
        if mode != "selection":
            raise ValueError("Phase 3C only supports mode='selection'")
        self.output_root = Path(output_root)
        self.feature_schema_version = feature_schema_version
        self.target_schema_version = target_schema_version
        self.mode = mode
        self.results: list[NonlinearResult] = []

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
        temporary.replace(path)

    def _manifest(
        self, profile: TreeProfile, task: str, approach: str, target_spec: TargetSpec,
        data: SelectionDataset, preprocessing: dict[str, Any], *, is_fit: bool,
        source_model_id: str | None = None,
    ) -> dict[str, Any]:
        identifier = experiment_id(profile, task, target_spec.horizon, approach)
        split = data.split_manifest
        full_parameters = dict(profile.parameters)
        if profile.family == "xgb":
            full_parameters["objective"] = "binary:logistic" if task == "classification" else "reg:squarederror"
            if task == "classification":
                full_parameters["eval_metric"] = "logloss"
        elif profile.family == "lgbm":
            full_parameters["objective"] = "binary" if task == "classification" else "regression"
            if task == "classification":
                full_parameters["class_weight"] = None
        elif task == "classification":
            full_parameters["class_weight"] = None
        return {
            "experiment_id": identifier, "model_id": identifier,
            "model_family": profile.family, "profile": profile.name,
            "complexity_order": profile.complexity, "task": task, "approach": approach,
            "target_name": target_spec.target_column, "horizon": target_spec.horizon,
            "feature_set_version": QUANTITATIVE_BASELINE_VERSION,
            "effective_feature_names": [row["transformed_feature"] for row in preprocessing["features"] if not row["excluded_as_degenerate"]],
            "excluded_degenerate_features": [row["transformed_feature"] for row in preprocessing["features"] if row["excluded_as_degenerate"]],
            "preprocessing_version": TREE_PREPROCESSING_VERSION,
            "train_start": split["dates"]["train"][0], "train_end": split["dates"]["train"][1],
            "validation_start": split["dates"]["validation"][0], "validation_end": split["dates"]["validation"][1],
            "purge_rule_version": split["purge_rule_version"], "embargo_sessions": split["embargo_sessions"],
            "model_hyperparameters": full_parameters,
            "feature_schema_version": self.feature_schema_version,
            "target_schema_version": self.target_schema_version,
            "sklearn_version": sklearn.__version__, "xgboost_version": xgboost.__version__,
            "lightgbm_version": lightgbm.__version__,
            "train_rows": int(len(data.train.y)), "validation_rows": int(len(data.validation.y)),
            "train_decision_dates": int(data.train.metadata["decision_date"].nunique()),
            "validation_decision_dates": int(data.validation.metadata["decision_date"].nunique()),
            "random_state": RANDOM_STATE, "is_fit": is_fit, "source_model_id": source_model_id,
            "generated_at": datetime.now(timezone.utc).isoformat(), **git_metadata(),
            "mode": self.mode, "test_used": False,
        }

    @staticmethod
    def _base_predictions(data: SelectionDataset, actual: pd.Series, prediction: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame({
            "ticker": data.validation.metadata["ticker"].to_numpy(),
            "decision_date": data.validation.metadata["decision_date"].to_numpy(),
            "actual": actual.to_numpy(), "prediction": prediction,
        })

    def _record(self, result: NonlinearResult) -> NonlinearResult:
        directory = self.output_root / result.experiment_id
        directory.mkdir(parents=True, exist_ok=True)
        self._write_json(directory / "manifest.json", result.manifest)
        self._write_json(directory / "metrics.json", result.metrics)
        self._write_json(directory / "preprocessing.json", result.preprocessing)
        result.predictions.to_parquet(directory / "validation_predictions.parquet", index=False)
        self.results.append(result)
        return result

    def run_models(
        self, data: SelectionDataset, target_spec: TargetSpec, *, task: str,
        actual_returns: pd.Series | None = None,
    ) -> list[NonlinearResult]:
        if tuple(data.train.X.columns) != QUANTITATIVE_BASELINE_FEATURES:
            raise ValueError("Phase 3C requires the exact 52-feature quantitative-baseline-v1 allowlist")
        preprocessor = TreePreprocessor(QUANTITATIVE_BASELINE_FEATURES)
        train_x = preprocessor.fit_transform(data.train.X)
        validation_x = preprocessor.transform(data.validation.X)
        preprocessing = preprocessor.metadata()
        results: list[NonlinearResult] = []
        for profile in TREE_PROFILES:
            estimator = profile.classifier() if task == "classification" else profile.regressor()
            estimator.fit(train_x, data.train.y)
            if task == "classification":
                probability = estimator.predict_proba(validation_x)[:, list(estimator.classes_).index(1)]
                metrics = _classification_bundle(data.train.y, data.validation.y, probability, data.validation.metadata)
                predictions = self._base_predictions(data, data.validation.y, probability).rename(columns={"prediction": "probability"})
                predictions["prediction"] = predictions["probability"]
                predictions["predicted_class"] = (predictions["probability"] >= 0.5).astype(int)
                approach = "model"
            else:
                prediction = np.asarray(estimator.predict(validation_x), dtype=float)
                if task == "regression":
                    metrics = _regression_bundle(data.validation.y.astype(float), prediction, data.validation.metadata)
                    predictions = self._base_predictions(data, data.validation.y, prediction)
                    approach = "model"
                else:
                    if actual_returns is None:
                        raise ValueError("ranking requires aligned actual returns")
                    metrics = _ranking_bundle(data.validation.y.astype(float), actual_returns, prediction, data.validation.metadata)
                    predictions = self._ranking_predictions(data, data.validation.y, actual_returns, prediction)
                    approach = "direct"
            manifest = self._manifest(profile, task, approach, target_spec, data, preprocessing, is_fit=True)
            result = NonlinearResult(
                manifest["experiment_id"], profile.family, profile.name, profile.complexity,
                task, approach, target_spec.horizon, metrics, manifest, predictions,
                preprocessing, True, estimator, preprocessor, validation_x,
                data.validation.y.reset_index(drop=True), data.validation.metadata.reset_index(drop=True),
            )
            results.append(self._record(result))
        return results

    @staticmethod
    def _ranking_predictions(
        data: SelectionDataset, actual_rank: pd.Series, actual_return: pd.Series, score: np.ndarray
    ) -> pd.DataFrame:
        frame = pd.DataFrame({
            "ticker": data.validation.metadata["ticker"].to_numpy(),
            "decision_date": data.validation.metadata["decision_date"].to_numpy(),
            "predicted_score": score, "actual_rank": actual_rank.to_numpy(),
            "actual_return": actual_return.to_numpy(),
        })
        frame["predicted_rank"] = cross_sectional_percentile_rank(frame["predicted_score"], frame["decision_date"])
        frame["prediction"] = frame["predicted_score"]
        frame["actual"] = frame["actual_rank"]
        return frame

    def derive_ranking(
        self, rank_data: SelectionDataset, target_spec: TargetSpec,
        actual_returns: pd.Series, regression_results: Sequence[NonlinearResult],
    ) -> list[NonlinearResult]:
        keys = rank_data.validation.metadata[["ticker", "decision_date"]].copy()
        results: list[NonlinearResult] = []
        for source in regression_results:
            source_frame = source.predictions[["ticker", "decision_date", "prediction"]]
            aligned = keys.merge(source_frame, on=["ticker", "decision_date"], how="left", validate="one_to_one")
            if aligned["prediction"].isna().any():
                raise ValueError(f"regression predictions do not align to ranking rows: {source.experiment_id}")
            score = aligned["prediction"].to_numpy(dtype=float)
            metrics = _ranking_bundle(rank_data.validation.y.astype(float), actual_returns, score, rank_data.validation.metadata)
            profile = next(item for item in TREE_PROFILES if item.family == source.family and item.name == source.profile)
            manifest = self._manifest(
                profile, "ranking", "predicted-return", target_spec, rank_data,
                source.preprocessing, is_fit=False, source_model_id=source.experiment_id,
            )
            result = NonlinearResult(
                manifest["experiment_id"], source.family, source.profile, source.complexity,
                "ranking", "predicted-return", target_spec.horizon, metrics, manifest,
                self._ranking_predictions(rank_data, rank_data.validation.y, actual_returns, score),
                source.preprocessing, False, source.model, source.preprocessor,
                source.validation_x, rank_data.validation.y.reset_index(drop=True),
                rank_data.validation.metadata.reset_index(drop=True),
            )
            results.append(self._record(result))
        return results

    @staticmethod
    def _native_importance(result: NonlinearResult) -> np.ndarray:
        model = result.model
        names = list(result.validation_x.columns)
        if result.family == "xgb":
            values = model.get_booster().get_score(importance_type="gain")
            return np.asarray([values.get(name, 0.0) for name in names], dtype=float)
        if result.family == "lgbm":
            return np.asarray(model.booster_.feature_importance(importance_type="gain"), dtype=float)
        return np.asarray(model.feature_importances_, dtype=float)

    def persist_feature_importance(self, result: NonlinearResult) -> Path:
        """Compute importance using only the selected model's validation partition."""
        if result.model is None or result.validation_x is None or result.validation_y is None:
            raise ValueError("selected result lacks fitted model or validation data")
        if result.task == "classification":
            scoring: Any = "roc_auc"
            metric_name = "roc_auc"
        elif result.task == "regression":
            scoring = "neg_root_mean_squared_error"
            metric_name = "negative_rmse"
        else:
            scoring = _RankICScorer(result.validation_metadata["decision_date"])
            metric_name = "mean_daily_spearman_rank_ic"
        permutation = permutation_importance(
            result.model, result.validation_x, result.validation_y,
            scoring=scoring, n_repeats=PERMUTATION_REPEATS,
            random_state=RANDOM_STATE, n_jobs=-1,
        )
        frame = pd.DataFrame({
            "feature": result.validation_x.columns,
            "native_importance": self._native_importance(result),
            "permutation_importance_mean": permutation.importances_mean,
            "permutation_importance_std": permutation.importances_std,
            "permutation_metric": metric_name,
        }).sort_values("permutation_importance_mean", ascending=False, kind="mergesort")
        destination = self.output_root / result.experiment_id / "feature_importance.parquet"
        destination.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(destination, index=False)
        result.manifest["feature_importance_validation_only"] = True
        self._write_json(destination.parent / "manifest.json", result.manifest)
        return destination

    @staticmethod
    def _summary_row(result: NonlinearResult, selected_family: set[str], selected_horizon: set[str]) -> dict[str, Any]:
        overall = result.metrics["overall"]
        ic = overall.get("daily_spearman", overall.get("rank_ic", {}))
        stability = result.metrics["stability"]
        return {
            "experiment_id": result.experiment_id, "task": result.task, "approach": result.approach,
            "horizon": result.horizon, "model_family": result.family, "profile": result.profile,
            "is_fit": result.is_fit, "primary_metric": _primary(result),
            "mean_ic": ic.get("mean"), "icir": ic.get("icir"),
            "pct_positive_ic": ic.get("pct_positive"),
            "rmse": overall.get("pooled", {}).get("rmse"), "roc_auc": overall.get("roc_auc"),
            "log_loss": overall.get("log_loss"), "balanced_accuracy": overall.get("balanced_accuracy"),
            "top10_uplift": overall.get("top10", {}).get("average_top10_uplift"),
            "worst_year_ic": stability.get("worst_year_ic"),
            "worst_year_auc": stability.get("worst_year_auc"),
            "year_metric_std": stability.get("year_ic_std", stability.get("year_auc_std")),
            "selected_within_family": result.experiment_id in selected_family,
            "selected_within_horizon": result.experiment_id in selected_horizon,
            "test_used": False,
        }

    def persist_summary(self, family_winners: Iterable[NonlinearResult], horizon_winners: Iterable[NonlinearResult]) -> pd.DataFrame:
        family_ids = {item.experiment_id for item in family_winners}
        horizon_ids = {item.experiment_id for item in horizon_winners}
        for result in self.results:
            result.manifest["selected_within_family"] = result.experiment_id in family_ids
            result.manifest["selected_within_horizon"] = result.experiment_id in horizon_ids
            self._write_json(self.output_root / result.experiment_id / "manifest.json", result.manifest)
        frame = pd.DataFrame([self._summary_row(item, family_ids, horizon_ids) for item in self.results])
        frame.to_csv(self.output_root / "summary.csv", index=False)
        frame.to_parquet(self.output_root / "summary.parquet", index=False)
        return frame

    def global_manifest(self) -> dict[str, Any]:
        return {
            "phase": "3C-nonlinear-predictive-models", "mode": self.mode,
            "feature_set_version": QUANTITATIVE_BASELINE_VERSION,
            "preprocessing_version": TREE_PREPROCESSING_VERSION,
            "feature_schema_version": self.feature_schema_version,
            "target_schema_version": self.target_schema_version,
            "sklearn_version": sklearn.__version__, "xgboost_version": xgboost.__version__,
            "lightgbm_version": lightgbm.__version__, "random_state": RANDOM_STATE,
            "permutation_repeats": PERMUTATION_REPEATS, "test_used": False,
            "generated_at": datetime.now(timezone.utc).isoformat(), **git_metadata(),
        }


def compact_result(result: NonlinearResult) -> dict[str, Any]:
    overall = result.metrics["overall"]
    ic = overall.get("daily_spearman", overall.get("rank_ic", {}))
    return {
        "experiment_id": result.experiment_id, "model_family": result.family,
        "profile": result.profile, "approach": result.approach,
        "mean_ic": ic.get("mean"), "icir": ic.get("icir"),
        "pct_positive_ic": ic.get("pct_positive"),
        "rmse": overall.get("pooled", {}).get("rmse"),
        "roc_auc": overall.get("roc_auc"), "log_loss": overall.get("log_loss"),
        "balanced_accuracy": overall.get("balanced_accuracy"),
        "top10_uplift": overall.get("top10", {}).get("average_top10_uplift"),
        **result.metrics["stability"], "by_year": result.metrics["by_year"],
    }


def compare_to_phase3b(task: str, nonlinear: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    """Compare a selected nonlinear result to a persisted (never retrained) 3B result."""
    if task == "classification":
        baseline_years = [baseline["by_year"][str(year)].get("roc_auc") for year in VALIDATION_YEARS]
        baseline_worst = min(value for value in baseline_years if value is not None)
        comparison = {
            "baseline_roc_auc": baseline.get("roc_auc"), "complex_roc_auc": nonlinear.get("roc_auc"),
            "delta_auc": nonlinear.get("roc_auc") - baseline.get("roc_auc"),
            "baseline_log_loss": baseline.get("log_loss"), "complex_log_loss": nonlinear.get("log_loss"),
            "delta_logloss": nonlinear.get("log_loss") - baseline.get("log_loss"),
            "baseline_balanced_accuracy": baseline.get("balanced_accuracy"),
            "complex_balanced_accuracy": nonlinear.get("balanced_accuracy"),
            "delta_balanced_accuracy": nonlinear.get("balanced_accuracy") - baseline.get("balanced_accuracy"),
            "baseline_worst_year_auc": baseline_worst, "complex_worst_year_auc": nonlinear.get("worst_year_auc"),
            "delta_worst_year_auc": nonlinear.get("worst_year_auc") - baseline_worst,
        }
    else:
        branch = "daily_spearman" if task == "regression" else "rank_ic"
        baseline_years = [baseline["by_year"][str(year)][branch]["mean"] for year in VALIDATION_YEARS]
        baseline_worst = min(baseline_years)
        comparison = {
            "baseline_mean_ic": baseline.get("mean_ic"), "complex_mean_ic": nonlinear.get("mean_ic"),
            "delta_mean_ic": nonlinear.get("mean_ic") - baseline.get("mean_ic"),
            "baseline_icir": baseline.get("icir"), "complex_icir": nonlinear.get("icir"),
            "delta_icir": nonlinear.get("icir") - baseline.get("icir"),
            "baseline_top10_uplift": baseline.get("top10_uplift"),
            "complex_top10_uplift": nonlinear.get("top10_uplift"),
            "delta_top10_uplift": nonlinear.get("top10_uplift") - baseline.get("top10_uplift"),
            "baseline_worst_year_ic": baseline_worst, "complex_worst_year_ic": nonlinear.get("worst_year_ic"),
            "delta_worst_year_ic": nonlinear.get("worst_year_ic") - baseline_worst,
        }
    return {**comparison, **improvement_flags(task, comparison)}
