import numpy as np
import pandas as pd
import pytest

from investment_system.models.nonlinear_profiles import TREE_PROFILES
from investment_system.models.phase3c import (
    AUC_TOLERANCE,
    IC_TOLERANCE,
    NonlinearResult,
    improvement_flags,
    select_candidate,
    stability_metrics,
)


def test_frozen_tree_profiles_have_exact_parameters_and_complexity_order() -> None:
    assert [item.profile_id for item in TREE_PROFILES] == [
        "rf-small", "rf-medium", "rf-wide", "xgb-small", "xgb-reg", "xgb-medium",
        "lgbm-small", "lgbm-reg", "lgbm-medium",
    ]
    profiles = {item.profile_id: item for item in TREE_PROFILES}
    assert profiles["rf-small"].parameters == {
        "n_estimators": 300, "max_depth": 4, "min_samples_leaf": 100,
        "max_features": "sqrt", "bootstrap": True, "random_state": 42, "n_jobs": -1,
    }
    assert profiles["rf-medium"].parameters["min_samples_leaf"] == 50
    assert profiles["rf-wide"].parameters["max_features"] == .5
    assert profiles["xgb-small"].parameters["min_child_weight"] == 20
    assert profiles["xgb-reg"].parameters["reg_alpha"] == 1
    assert profiles["xgb-medium"].parameters["n_estimators"] == 500
    assert profiles["lgbm-small"].parameters["num_leaves"] == 15
    assert profiles["lgbm-reg"].parameters["min_child_samples"] == 150
    assert profiles["lgbm-medium"].parameters["num_leaves"] == 31
    for profile in TREE_PROFILES:
        assert profile.parameters["random_state"] == 42
        assert profile.parameters["n_jobs"] == -1
    assert profiles["xgb-small"].regressor().get_params()["objective"] == "reg:squarederror"
    assert profiles["xgb-small"].classifier().get_params()["eval_metric"] == "logloss"
    assert profiles["lgbm-small"].regressor().get_params()["objective"] == "regression"
    assert profiles["lgbm-small"].classifier().get_params()["objective"] == "binary"


def _candidate(task: str, name: str, primary: float, secondary: float, complexity: int = 0):
    if task == "classification":
        metrics = {
            "overall": {"roc_auc": primary, "log_loss": secondary, "balanced_accuracy": .55},
            "stability": {"worst_year_auc": .51},
        }
    else:
        branch = "daily_spearman" if task == "regression" else "rank_ic"
        metrics = {
            "overall": {branch: {"mean": primary, "icir": secondary, "pct_positive": .52}},
            "stability": {"worst_year_ic": -.01},
        }
    return NonlinearResult(
        name, "rf", name, complexity, task, "model", 10, metrics, {}, pd.DataFrame(), {}, True,
    )


def test_selection_uses_tolerance_stability_and_complexity() -> None:
    assert IC_TOLERANCE == AUC_TOLERANCE == .001
    assert select_candidate([
        _candidate("regression", "higher-primary", .0200, .05, 2),
        _candidate("regression", "better-icir", .0195, .20, 1),
    ]).experiment_id == "better-icir"
    assert select_candidate([
        _candidate("classification", "better-auc", .7000, .70, 2),
        _candidate("classification", "better-loss", .6995, .60, 1),
    ]).experiment_id == "better-loss"
    tied = [_candidate("ranking", "complex", .02, .1, 2), _candidate("ranking", "simple", .02, .1, 0)]
    assert select_candidate(tied).experiment_id == "simple"


def test_stability_and_material_flags_are_explicit() -> None:
    metrics = {"by_year": {
        "2019": {"daily_spearman": {"mean": .01}},
        "2020": {"daily_spearman": {"mean": .08}},
        "2021": {"daily_spearman": {"mean": -.02}},
    }}
    stability = stability_metrics(metrics, "regression")
    assert stability["worst_year_ic"] == -.02
    assert stability["year_ic_std"] == pytest.approx(np.std([.01, .08, -.02], ddof=1))
    flags = improvement_flags("regression", {"delta_mean_ic": .005, "delta_worst_year_ic": -.001})
    assert flags == {"numerical_improvement": True, "material_improvement": True, "stability_improvement": False}


def test_each_official_family_is_deterministic_on_synthetic_data() -> None:
    x = pd.DataFrame({"a": np.arange(40), "b": np.sin(np.arange(40))})
    y_reg = pd.Series(np.cos(np.arange(40)))
    y_cls = pd.Series([0, 1] * 20)
    for family in ("rf", "xgb", "lgbm"):
        profile = next(item for item in TREE_PROFILES if item.family == family and item.name == "small")
        first_reg = profile.regressor().fit(x, y_reg).predict(x)
        second_reg = profile.regressor().fit(x, y_reg).predict(x)
        np.testing.assert_allclose(first_reg, second_reg, rtol=1e-14, atol=1e-14)
        first_cls = profile.classifier().fit(x, y_cls).predict_proba(x)
        second_cls = profile.classifier().fit(x, y_cls).predict_proba(x)
        np.testing.assert_allclose(first_cls, second_cls, rtol=1e-14, atol=1e-14)
