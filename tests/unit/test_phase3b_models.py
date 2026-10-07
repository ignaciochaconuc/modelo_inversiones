from datetime import date

import numpy as np
import pandas as pd
import pytest
from sklearn.linear_model import LogisticRegression, Ridge

from investment_system.models.baselines import TrainMeanPredictor, TrainPriorPredictor, ZeroPredictor
from investment_system.models.contracts import TargetSpec
from investment_system.models.metrics import (
    classification_metrics,
    cross_sectional_percentile_rank,
    daily_correlations,
    ranking_metrics,
    regression_metrics,
    top_k_diagnostics,
)
from investment_system.models.phase3b import (
    AUC_TOLERANCE,
    IC_TOLERANCE,
    ExperimentResult,
    Phase3BSelectionRunner,
    SelectionDataset,
    model_id,
    select_direct_rank_ridge,
    select_logistic,
    select_ridge,
)
from investment_system.models.preprocessing import BaselinePreprocessor
from investment_system.models.supervised import SupervisedPartition


def test_naive_baselines_use_train_statistics() -> None:
    train_x = pd.DataFrame({"x": [1, 2, 3]})
    validation_x = pd.DataFrame({"x": [100, 200]})
    assert ZeroPredictor().fit(train_x, pd.Series([2, 4, 6])).predict(validation_x).tolist() == [0, 0]
    assert TrainMeanPredictor().fit(train_x, pd.Series([2, 4, 6])).predict(validation_x).tolist() == [4, 4]
    prior = TrainPriorPredictor().fit(train_x, pd.Series([0, 1, 1]))
    assert prior.predict_proba(validation_x)[:, 1].tolist() == pytest.approx([2 / 3, 2 / 3])


def test_regression_classification_and_ranking_metrics_are_explicit() -> None:
    dates = pd.Series([date(2020, 1, 2)] * 3 + [date(2020, 1, 3)] * 3)
    actual = pd.Series([1, 2, 3, 3, 2, 1], dtype=float)
    predicted = np.array([1, 2, 3, 3, 2, 1], dtype=float)
    regression = regression_metrics(actual, predicted, dates)
    assert regression["pooled"]["rmse"] == 0
    assert regression["daily_spearman"]["mean"] == pytest.approx(1)
    assert regression["daily_spearman"]["icir"] is None

    classification = classification_metrics(pd.Series([0, 0, 1, 1]), np.array([.1, .2, .8, .9]))
    assert classification["roc_auc"] == 1
    assert classification["log_loss"] < 0.3
    degenerate = classification_metrics(pd.Series([1, 1]), np.array([.8, .9]))
    assert degenerate["roc_auc"] is None and degenerate["degenerate_reason"]

    ranking = ranking_metrics(actual, actual, predicted, dates)
    assert ranking["rank_ic"]["mean"] == pytest.approx(1)
    assert top_k_diagnostics(actual, predicted, dates, k=10)["dates"] == 0
    constant_dates = pd.Series([date(2020, 1, 2)] * 10)
    assert top_k_diagnostics(
        pd.Series(range(10), dtype=float), pd.Series([0.0] * 10), constant_dates, k=10
    )["average_top10_uplift"] is None


def test_daily_ic_skips_degenerate_dates_and_ranks_ties_with_average() -> None:
    dates = pd.Series([date(2020, 1, 2)] * 3 + [date(2020, 1, 3)] * 3)
    correlations = daily_correlations(
        pd.Series([1, 2, 3, 1, 2, 3]), pd.Series([1, 2, 3, 1, 1, 1]), dates,
        method="spearman",
    )
    assert len(correlations) == 1 and correlations.iloc[0] == pytest.approx(1)
    ranks = cross_sectional_percentile_rank(
        pd.Series([1.0, 2.0, 2.0, 3.0]), pd.Series([date(2020, 1, 2)] * 4)
    )
    assert ranks.tolist() == pytest.approx([0, 0.5, 0.5, 1])


def _candidate(family: str, hyperparameter: float, metrics: dict) -> ExperimentResult:
    return ExperimentResult(
        experiment_id=f"{family}-{hyperparameter}", task="regression", horizon=10,
        model_family=family, hyperparameter=hyperparameter, metrics=metrics,
        validation_predictions=pd.DataFrame(), coefficients=None,
        preprocessing={"preprocessing_version": "x"}, manifest={},
    )


def test_predeclared_selection_tolerances_prefer_more_regularization() -> None:
    def regression_candidate(alpha, ic, icir=1, pct=.5, rmse=.1):
        return _candidate("ridge", alpha, {"overall": {
            "daily_spearman": {"mean": ic, "icir": icir, "pct_positive": pct},
            "pooled": {"rmse": rmse}, "rank_ic": {"mean": ic, "icir": icir, "pct_positive": pct},
            "top10": {"average_top10_uplift": .01},
        }})
    assert IC_TOLERANCE == .001
    assert select_ridge([regression_candidate(.01, .10), regression_candidate(100, .0995)]).hyperparameter == 100
    assert select_direct_rank_ridge([
        regression_candidate(.01, .10), regression_candidate(100, .0995)
    ]).hyperparameter == 100

    def logistic_candidate(c, auc, loss):
        return _candidate("logistic", c, {"overall": {
            "roc_auc": auc, "log_loss": loss, "balanced_accuracy": .5,
        }})
    assert AUC_TOLERANCE == .001
    assert select_logistic([logistic_candidate(.01, .7995, .7), logistic_candidate(100, .8, .6)]).hyperparameter == .01


def test_ids_and_repeated_standardized_ridge_logistic_runs_are_deterministic() -> None:
    assert model_id("ridge", "regression", 10, 1) == model_id("ridge", "regression", 10, 1)
    x = pd.DataFrame({"return_1d": [0., 1., 2., 3.], "return_2d": [3., 2., 1., 0.]})
    y_reg = pd.Series([0., 1., 2., 3.])
    y_cls = pd.Series([0, 0, 1, 1])
    predictions = []
    probabilities = []
    for _ in range(2):
        processed = BaselinePreprocessor(x.columns).fit_transform(x)
        predictions.append(Ridge(alpha=1).fit(processed, y_reg).predict(processed))
        probabilities.append(LogisticRegression(C=1, random_state=42).fit(processed, y_cls).predict_proba(processed)[:, 1])
    np.testing.assert_array_equal(predictions[0], predictions[1])
    np.testing.assert_array_equal(probabilities[0], probabilities[1])


def test_selection_contract_has_no_test_and_runner_rejects_other_modes(tmp_path) -> None:
    partition = SupervisedPartition(pd.DataFrame(), pd.Series(dtype=float), pd.DataFrame())
    selection = SelectionDataset(partition, partition, {})
    assert not hasattr(selection, "test")
    with pytest.raises(ValueError, match="selection"):
        Phase3BSelectionRunner(tmp_path, feature_schema_version="4", target_schema_version="v3", mode="test")
