"""Phase 3B simple predictive baselines using TRAIN and VALIDATION only."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Callable, Sequence

import numpy as np
import pandas as pd
import sklearn
from sklearn.linear_model import LinearRegression, LogisticRegression, Ridge

from investment_system.core.reproducibility import git_metadata
from investment_system.models.baselines import TrainMeanPredictor, TrainPriorPredictor, ZeroPredictor
from investment_system.models.contracts import TargetSpec
from investment_system.models.feature_sets import (
    QUANTITATIVE_BASELINE_FEATURES,
    QUANTITATIVE_BASELINE_VERSION,
)
from investment_system.models.metrics import (
    classification_metrics,
    cross_sectional_percentile_rank,
    ranking_metrics,
    regression_metrics,
)
from investment_system.models.preprocessing import BaselinePreprocessor, PREPROCESSING_VERSION
from investment_system.models.supervised import PURGE_RULE_VERSION, SupervisedPartition

RIDGE_ALPHAS = (0.01, 0.1, 1.0, 10.0, 100.0)
LOGISTIC_CS = (0.01, 0.1, 1.0, 10.0, 100.0)
IC_TOLERANCE = 0.001
AUC_TOLERANCE = 0.001
RANDOM_STATE = 42


@dataclass(frozen=True)
class SelectionDataset:
    """The sealed-test boundary: this contract has no test partition."""

    train: SupervisedPartition
    validation: SupervisedPartition
    split_manifest: dict[str, Any]


@dataclass
class ExperimentResult:
    experiment_id: str
    task: str
    horizon: int
    model_family: str
    hyperparameter: float | None
    metrics: dict[str, Any]
    validation_predictions: pd.DataFrame
    coefficients: pd.DataFrame | None
    preprocessing: dict[str, Any]
    manifest: dict[str, Any]


def selection_dataset(supervised: Any) -> SelectionDataset:
    """Copy only train/validation references; test cannot reach the selection runner."""
    return SelectionDataset(
        train=supervised.train,
        validation=supervised.validation,
        split_manifest=supervised.manifest,
    )


def _number_slug(value: float) -> str:
    return f"{value:g}".replace(".", "p")


def model_id(model_family: str, task: str, horizon: int, hyperparameter: float | None = None) -> str:
    suffix = ""
    if hyperparameter is not None:
        name = "a" if "ridge" in model_family else "c"
        suffix = f"-{name}{_number_slug(hyperparameter)}"
    return (
        f"{model_family}-{task}-{horizon}d{suffix}-"
        f"qbaselinev1-prepv1"
    )


def _metric_value(candidate: ExperimentResult, path: Sequence[str], default: float) -> float:
    value: Any = candidate.metrics
    for key in path:
        value = value.get(key) if isinstance(value, dict) else None
    return float(value) if value is not None and np.isfinite(value) else default


def select_ridge(candidates: Sequence[ExperimentResult]) -> ExperimentResult:
    best_ic = max(_metric_value(item, ("overall", "daily_spearman", "mean"), -np.inf) for item in candidates)
    close = [
        item for item in candidates
        if _metric_value(item, ("overall", "daily_spearman", "mean"), -np.inf)
        >= best_ic - IC_TOLERANCE
    ]
    return max(close, key=lambda item: (
        item.hyperparameter or 0,
        _metric_value(item, ("overall", "daily_spearman", "icir"), -np.inf),
        _metric_value(item, ("overall", "daily_spearman", "pct_positive"), -np.inf),
        -_metric_value(item, ("overall", "pooled", "rmse"), np.inf),
    ))


def select_logistic(candidates: Sequence[ExperimentResult]) -> ExperimentResult:
    best_auc = max(_metric_value(item, ("overall", "roc_auc"), -np.inf) for item in candidates)
    close = [
        item for item in candidates
        if _metric_value(item, ("overall", "roc_auc"), -np.inf) >= best_auc - AUC_TOLERANCE
    ]
    return min(close, key=lambda item: (
        item.hyperparameter if item.hyperparameter is not None else np.inf,
        _metric_value(item, ("overall", "log_loss"), np.inf),
        -_metric_value(item, ("overall", "balanced_accuracy"), -np.inf),
    ))


def select_direct_rank_ridge(candidates: Sequence[ExperimentResult]) -> ExperimentResult:
    best_ic = max(_metric_value(item, ("overall", "rank_ic", "mean"), -np.inf) for item in candidates)
    close = [
        item for item in candidates
        if _metric_value(item, ("overall", "rank_ic", "mean"), -np.inf)
        >= best_ic - IC_TOLERANCE
    ]
    return max(close, key=lambda item: (
        item.hyperparameter or 0,
        _metric_value(item, ("overall", "rank_ic", "icir"), -np.inf),
        _metric_value(item, ("overall", "rank_ic", "pct_positive"), -np.inf),
        _metric_value(item, ("overall", "top10", "average_top10_uplift"), -np.inf),
    ))


def select_ranking_approach(candidates: Sequence[ExperimentResult]) -> ExperimentResult:
    return max(candidates, key=lambda item: (
        _metric_value(item, ("overall", "rank_ic", "mean"), -np.inf),
        _metric_value(item, ("overall", "rank_ic", "icir"), -np.inf),
        _metric_value(item, ("overall", "rank_ic", "pct_positive"), -np.inf),
        _metric_value(item, ("overall", "top10", "average_top10_uplift"), -np.inf),
        item.experiment_id,
    ))


def _by_year(
    actual: pd.Series,
    predicted: np.ndarray,
    metadata: pd.DataFrame,
    evaluator: Callable[[pd.Series, np.ndarray, pd.Series], dict[str, Any]],
) -> dict[str, Any]:
    years = pd.to_datetime(metadata["decision_date"]).dt.year
    result: dict[str, Any] = {}
    for year in (2019, 2020, 2021):
        mask = years.eq(year).to_numpy()
        result[str(year)] = evaluator(
            actual.loc[mask].reset_index(drop=True), predicted[mask],
            metadata.loc[mask, "decision_date"].reset_index(drop=True),
        )
    return result


def _regression_metric_bundle(
    actual: pd.Series, predicted: np.ndarray, metadata: pd.DataFrame
) -> dict[str, Any]:
    evaluator = lambda y, p, d: regression_metrics(y, p, d)
    return {
        "overall": evaluator(actual, predicted, metadata["decision_date"]),
        "by_year": _by_year(actual, predicted, metadata, evaluator),
        "primary_selection_metric": "mean_daily_cross_sectional_spearman_ic",
        "tie_breaking": ["icir", "pct_days_ic_positive", "rmse", "larger_alpha_within_0.001"],
    }


def _classification_metric_bundle(
    train_actual: pd.Series,
    validation_actual: pd.Series,
    probability: np.ndarray,
    metadata: pd.DataFrame,
) -> dict[str, Any]:
    years = pd.to_datetime(metadata["decision_date"]).dt.year
    by_year = {
        str(year): classification_metrics(
            validation_actual.loc[years.eq(year).to_numpy()].reset_index(drop=True),
            probability[years.eq(year).to_numpy()],
        )
        for year in (2019, 2020, 2021)
    }
    return {
        "overall": classification_metrics(validation_actual, probability),
        "by_year": by_year,
        "train_positive_prevalence": float(train_actual.astype(float).mean()),
        "validation_positive_prevalence": float(validation_actual.astype(float).mean()),
        "primary_selection_metric": "roc_auc",
        "tie_breaking": ["log_loss", "balanced_accuracy", "smaller_C_within_0.001"],
    }


def _ranking_metric_bundle(
    actual_rank: pd.Series,
    actual_return: pd.Series,
    predicted_score: np.ndarray,
    metadata: pd.DataFrame,
) -> dict[str, Any]:
    def evaluate(mask: np.ndarray) -> dict[str, Any]:
        return ranking_metrics(
            actual_rank.loc[mask].reset_index(drop=True),
            actual_return.loc[mask].reset_index(drop=True),
            predicted_score[mask],
            metadata.loc[mask, "decision_date"].reset_index(drop=True),
        )
    all_mask = np.ones(len(actual_rank), dtype=bool)
    years = pd.to_datetime(metadata["decision_date"]).dt.year
    return {
        "overall": evaluate(all_mask),
        "by_year": {str(year): evaluate(years.eq(year).to_numpy()) for year in (2019, 2020, 2021)},
        "primary_selection_metric": "mean_daily_cross_sectional_spearman_rank_ic",
        "tie_breaking": ["icir", "pct_days_ic_positive", "top10_future_return_uplift"],
    }


def _coefficient_frame(feature_names: Sequence[str], coefficients: np.ndarray, intercept: float) -> pd.DataFrame:
    return pd.DataFrame({
        "feature": [*feature_names, "__intercept__"],
        "coefficient": [*np.asarray(coefficients, dtype=float).tolist(), float(intercept)],
    })


class Phase3BSelectionRunner:
    """Run predefined simple models. This object cannot receive a test partition."""

    def __init__(
        self,
        output_root: str | Path,
        *,
        feature_schema_version: str,
        target_schema_version: str,
        mode: str = "selection",
    ) -> None:
        if mode != "selection":
            raise ValueError("Phase 3B only supports mode='selection'")
        self.output_root = Path(output_root)
        self.feature_schema_version = feature_schema_version
        self.target_schema_version = target_schema_version
        self.mode = mode
        self.results: list[ExperimentResult] = []

    def _manifest(
        self,
        experiment_id: str,
        model_family: str,
        target_spec: TargetSpec,
        data: SelectionDataset,
        preprocessing: dict[str, Any],
        hyperparameters: dict[str, Any],
    ) -> dict[str, Any]:
        split = data.split_manifest
        return {
            "experiment_id": experiment_id,
            "model_id": experiment_id,
            "model_family": model_family,
            "task": target_spec.task.value,
            "target_name": target_spec.target_column,
            "horizon": target_spec.horizon,
            "feature_set_version": QUANTITATIVE_BASELINE_VERSION,
            "effective_feature_names": [
                row["transformed_feature"] for row in preprocessing.get("features", [])
                if not row.get("excluded_as_degenerate", False)
            ],
            "excluded_degenerate_features": [
                row["transformed_feature"] for row in preprocessing.get("features", [])
                if row.get("excluded_as_degenerate", False)
            ],
            "preprocessing_version": preprocessing["preprocessing_version"],
            "train_start": split["dates"]["train"][0],
            "train_end": split["dates"]["train"][1],
            "validation_start": split["dates"]["validation"][0],
            "validation_end": split["dates"]["validation"][1],
            "purge_rule_version": split["purge_rule_version"],
            "embargo_sessions": split["embargo_sessions"],
            "model_hyperparameters": hyperparameters,
            "target_schema_version": self.target_schema_version,
            "feature_schema_version": self.feature_schema_version,
            "train_rows": int(len(data.train.y)),
            "validation_rows": int(len(data.validation.y)),
            "train_decision_dates": int(data.train.metadata["decision_date"].nunique()),
            "validation_decision_dates": int(data.validation.metadata["decision_date"].nunique()),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **git_metadata(),
            "mode": self.mode,
            "test_used": False,
        }

    @staticmethod
    def _no_preprocessing(feature: str | None = None) -> dict[str, Any]:
        return {
            "preprocessing_version": "none",
            "fit_partition": "none",
            "features": [] if feature is None else [{
                "original_feature": feature, "transformed_feature": feature,
                "transformation": "identity", "train_median": None,
                "scaler_mean": None, "scaler_std": None,
                "excluded_as_degenerate": False,
            }],
        }

    def _record(
        self,
        *,
        model_family: str,
        target_spec: TargetSpec,
        data: SelectionDataset,
        metrics: dict[str, Any],
        predictions: pd.DataFrame,
        preprocessing: dict[str, Any],
        hyperparameters: dict[str, Any],
        coefficients: pd.DataFrame | None = None,
        hyperparameter: float | None = None,
        task_label: str | None = None,
    ) -> ExperimentResult:
        task = task_label or target_spec.task.value
        experiment_id = model_id(model_family, task, target_spec.horizon, hyperparameter)
        result = ExperimentResult(
            experiment_id=experiment_id,
            task=task,
            horizon=target_spec.horizon,
            model_family=model_family,
            hyperparameter=hyperparameter,
            metrics=metrics,
            validation_predictions=predictions,
            coefficients=coefficients,
            preprocessing=preprocessing,
            manifest=self._manifest(
                experiment_id, model_family, target_spec, data, preprocessing, hyperparameters
            ),
        )
        result.manifest["task"] = task
        self.results.append(result)
        return result

    @staticmethod
    def _base_predictions(data: SelectionDataset, actual: pd.Series, prediction: np.ndarray) -> pd.DataFrame:
        return pd.DataFrame({
            "ticker": data.validation.metadata["ticker"].to_numpy(),
            "decision_date": data.validation.metadata["decision_date"].to_numpy(),
            "actual": actual.to_numpy(),
            "prediction": prediction,
        })

    def run_regression(
        self, data: SelectionDataset, target_spec: TargetSpec
    ) -> dict[str, Any]:
        train_y = data.train.y.astype(float)
        validation_y = data.validation.y.astype(float)
        naive: list[ExperimentResult] = []
        for family, predictor in (("zero", ZeroPredictor()), ("train_mean", TrainMeanPredictor())):
            predictor.fit(data.train.X, train_y)
            prediction = predictor.predict(data.validation.X)
            intercept = 0.0 if family == "zero" else float(predictor.mean_)
            naive.append(self._record(
                model_family=family, target_spec=target_spec, data=data,
                metrics=_regression_metric_bundle(validation_y, prediction, data.validation.metadata),
                predictions=self._base_predictions(data, validation_y, prediction),
                preprocessing=self._no_preprocessing(), hyperparameters={},
                coefficients=_coefficient_frame([], np.array([]), intercept),
            ))

        preprocessor = BaselinePreprocessor(QUANTITATIVE_BASELINE_FEATURES)
        train_x = preprocessor.fit_transform(data.train.X)
        validation_x = preprocessor.transform(data.validation.X)
        prep_metadata = preprocessor.metadata()
        linear = LinearRegression().fit(train_x, train_y)
        linear_prediction = linear.predict(validation_x)
        ols = self._record(
            model_family="ols", target_spec=target_spec, data=data,
            metrics=_regression_metric_bundle(validation_y, linear_prediction, data.validation.metadata),
            predictions=self._base_predictions(data, validation_y, linear_prediction),
            preprocessing=prep_metadata, hyperparameters={},
            coefficients=_coefficient_frame(train_x.columns, linear.coef_, linear.intercept_),
        )
        ridge_results = []
        for alpha in RIDGE_ALPHAS:
            model = Ridge(alpha=alpha).fit(train_x, train_y)
            prediction = model.predict(validation_x)
            ridge_results.append(self._record(
                model_family="ridge", target_spec=target_spec, data=data,
                metrics=_regression_metric_bundle(validation_y, prediction, data.validation.metadata),
                predictions=self._base_predictions(data, validation_y, prediction),
                preprocessing=prep_metadata, hyperparameters={"alpha": alpha},
                coefficients=_coefficient_frame(train_x.columns, model.coef_, model.intercept_),
                hyperparameter=alpha,
            ))
        return {
            "naive": naive,
            "ols": ols,
            "ridge": ridge_results,
            "best_ridge": select_ridge(ridge_results),
        }

    def run_classification(
        self, data: SelectionDataset, target_spec: TargetSpec
    ) -> dict[str, Any]:
        train_y = data.train.y.astype(int)
        validation_y = data.validation.y.astype(int)
        prior = TrainPriorPredictor().fit(data.train.X, train_y)
        prior_probability = prior.predict_proba(data.validation.X)[:, 1]
        prior_frame = self._base_predictions(data, validation_y, prior_probability).rename(
            columns={"prediction": "probability"}
        )
        prior_frame["prediction"] = prior_frame["probability"]
        prior_frame["predicted_class"] = (prior_frame["probability"] >= 0.5).astype(int)
        prior_result = self._record(
            model_family="train_prior", target_spec=target_spec, data=data,
            metrics=_classification_metric_bundle(train_y, validation_y, prior_probability, data.validation.metadata),
            predictions=prior_frame, preprocessing=self._no_preprocessing(), hyperparameters={},
            coefficients=_coefficient_frame([], np.array([]), float(prior.prior_)),
        )

        preprocessor = BaselinePreprocessor(QUANTITATIVE_BASELINE_FEATURES)
        train_x = preprocessor.fit_transform(data.train.X)
        validation_x = preprocessor.transform(data.validation.X)
        prep_metadata = preprocessor.metadata()
        candidates = []
        for c_value in LOGISTIC_CS:
            model = LogisticRegression(
                C=c_value, l1_ratio=0.0, class_weight=None, max_iter=1000,
                solver="lbfgs", random_state=RANDOM_STATE,
            ).fit(train_x, train_y)
            probability = model.predict_proba(validation_x)[:, list(model.classes_).index(1)]
            frame = self._base_predictions(data, validation_y, probability).rename(
                columns={"prediction": "probability"}
            )
            frame["prediction"] = frame["probability"]
            frame["predicted_class"] = (frame["probability"] >= 0.5).astype(int)
            candidates.append(self._record(
                model_family="logistic", target_spec=target_spec, data=data,
                metrics=_classification_metric_bundle(train_y, validation_y, probability, data.validation.metadata),
                predictions=frame, preprocessing=prep_metadata,
                hyperparameters={"C": c_value, "penalty": "l2", "l1_ratio": 0.0,
                                 "class_weight": None,
                                 "solver": "lbfgs", "random_state": RANDOM_STATE},
                coefficients=_coefficient_frame(train_x.columns, model.coef_[0], model.intercept_[0]),
                hyperparameter=c_value,
            ))
        return {"prior": prior_result, "logistic": candidates, "best_logistic": select_logistic(candidates)}

    def run_ranking(
        self,
        data: SelectionDataset,
        target_spec: TargetSpec,
        train_actual_return: pd.Series,
        validation_actual_return: pd.Series,
        regression_results: dict[str, Any],
    ) -> dict[str, Any]:
        actual_rank = data.validation.y.astype(float)
        validation_return = validation_actual_return.astype(float).reset_index(drop=True)

        def ranking_frame(scores: np.ndarray) -> pd.DataFrame:
            frame = pd.DataFrame({
                "ticker": data.validation.metadata["ticker"].to_numpy(),
                "decision_date": data.validation.metadata["decision_date"].to_numpy(),
                "predicted_score": scores,
                "actual_rank": actual_rank.to_numpy(),
                "actual_return": validation_return.to_numpy(),
            })
            frame["predicted_rank"] = cross_sectional_percentile_rank(
                frame["predicted_score"], frame["decision_date"]
            )
            frame["prediction"] = frame["predicted_score"]
            frame["actual"] = frame["actual_rank"]
            return frame

        momentum_scores = data.validation.X["momentum_20d"].astype(float).to_numpy()
        momentum = self._record(
            model_family="momentum20", target_spec=target_spec, data=data,
            metrics=_ranking_metric_bundle(actual_rank, validation_return, momentum_scores, data.validation.metadata),
            predictions=ranking_frame(momentum_scores), preprocessing=self._no_preprocessing("momentum_20d"),
            hyperparameters={}, task_label="ranking",
        )

        predicted_return_results = []
        for source in (regression_results["ols"], regression_results["best_ridge"]):
            source_frame = source.validation_predictions[["ticker", "decision_date", "prediction"]]
            aligned = data.validation.metadata[["ticker", "decision_date"]].merge(
                source_frame, on=["ticker", "decision_date"], how="left", validate="one_to_one"
            )
            if aligned["prediction"].isna().any():
                raise ValueError("regression scores do not cover the ranking validation cross-section")
            scores = aligned["prediction"].to_numpy(dtype=float)
            family = f"predicted_return_{source.model_family}"
            result = self._record(
                model_family=family, target_spec=target_spec, data=data,
                metrics=_ranking_metric_bundle(actual_rank, validation_return, scores, data.validation.metadata),
                predictions=ranking_frame(scores), preprocessing=source.preprocessing,
                hyperparameters=source.manifest["model_hyperparameters"],
                coefficients=source.coefficients, task_label="ranking",
                hyperparameter=source.hyperparameter,
            )
            result.manifest.update({
                "source_model_id": source.experiment_id,
                "source_target_name": source.manifest["target_name"],
                "train_rows": source.manifest["train_rows"],
                "train_decision_dates": source.manifest["train_decision_dates"],
            })
            predicted_return_results.append(result)

        preprocessor = BaselinePreprocessor(QUANTITATIVE_BASELINE_FEATURES)
        train_x = preprocessor.fit_transform(data.train.X)
        validation_x = preprocessor.transform(data.validation.X)
        prep_metadata = preprocessor.metadata()
        train_rank = data.train.y.astype(float)
        linear = LinearRegression().fit(train_x, train_rank)
        linear_scores = linear.predict(validation_x)
        direct_ols = self._record(
            model_family="direct_rank_ols", target_spec=target_spec, data=data,
            metrics=_ranking_metric_bundle(actual_rank, validation_return, linear_scores, data.validation.metadata),
            predictions=ranking_frame(linear_scores), preprocessing=prep_metadata, hyperparameters={},
            coefficients=_coefficient_frame(train_x.columns, linear.coef_, linear.intercept_),
            task_label="ranking",
        )
        direct_ridge = []
        for alpha in RIDGE_ALPHAS:
            model = Ridge(alpha=alpha).fit(train_x, train_rank)
            scores = model.predict(validation_x)
            direct_ridge.append(self._record(
                model_family="ridge", target_spec=target_spec, data=data,
                metrics=_ranking_metric_bundle(actual_rank, validation_return, scores, data.validation.metadata),
                predictions=ranking_frame(scores), preprocessing=prep_metadata,
                hyperparameters={"alpha": alpha},
                coefficients=_coefficient_frame(train_x.columns, model.coef_, model.intercept_),
                hyperparameter=alpha, task_label="ranking",
            ))
        best_direct_ridge = select_direct_rank_ridge(direct_ridge)
        approaches = [momentum, *predicted_return_results, direct_ols, best_direct_ridge]
        return {
            "momentum": momentum,
            "predicted_return": predicted_return_results,
            "direct_ols": direct_ols,
            "direct_ridge": direct_ridge,
            "best_direct_ridge": best_direct_ridge,
            "best_approach": select_ranking_approach(approaches),
        }

    @staticmethod
    def _write_json(path: Path, value: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp")
        temporary.write_text(json.dumps(value, indent=2, default=str, allow_nan=False), encoding="utf-8")
        temporary.replace(path)

    @staticmethod
    def _write_parquet(path: Path, frame: pd.DataFrame) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp.parquet")
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)

    def persist_experiments(self, selected_ids: set[str]) -> pd.DataFrame:
        summary_rows = []
        for result in self.results:
            directory = self.output_root / result.experiment_id
            result.manifest["selected_within_horizon"] = result.experiment_id in selected_ids
            self._write_json(directory / "manifest.json", result.manifest)
            self._write_json(directory / "metrics.json", result.metrics)
            self._write_json(directory / "preprocessing.json", result.preprocessing)
            self._write_parquet(directory / "validation_predictions.parquet", result.validation_predictions)
            if result.coefficients is not None:
                self._write_parquet(directory / "coefficients.parquet", result.coefficients)
            overall = result.metrics["overall"]
            daily = overall.get("daily_spearman", overall.get("rank_ic", {}))
            pooled = overall.get("pooled", {})
            top10 = overall.get("top10", {})
            summary_rows.append({
                "experiment_id": result.experiment_id,
                "task": result.task,
                "horizon": result.horizon,
                "model_family": result.model_family,
                "hyperparameter": result.hyperparameter,
                "primary_metric": result.metrics["primary_selection_metric"],
                "mean_ic": daily.get("mean"),
                "icir": daily.get("icir"),
                "pct_positive_ic": daily.get("pct_positive"),
                "rmse": pooled.get("rmse"),
                "roc_auc": overall.get("roc_auc"),
                "log_loss": overall.get("log_loss"),
                "top10_uplift": top10.get("average_top10_uplift"),
                "selected_within_horizon": result.experiment_id in selected_ids,
                "test_used": False,
            })
        summary = pd.DataFrame(summary_rows).sort_values(["task", "horizon", "experiment_id"])
        self._write_parquet(self.output_root / "summary.parquet", summary)
        summary.to_csv(self.output_root / "summary.csv", index=False)
        return summary

    def global_manifest(self) -> dict[str, Any]:
        return {
            "phase": "3B-simple-predictive-baselines",
            "mode": self.mode,
            "feature_set_version": QUANTITATIVE_BASELINE_VERSION,
            "preprocessing_version": PREPROCESSING_VERSION,
            "feature_schema_version": self.feature_schema_version,
            "target_schema_version": self.target_schema_version,
            "sklearn_version": sklearn.__version__,
            "random_state": RANDOM_STATE,
            "test_used": False,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            **git_metadata(),
        }
