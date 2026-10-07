"""Frozen Phase 3C tree-model profiles and official estimator factories."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from lightgbm import LGBMClassifier, LGBMRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
from xgboost import XGBClassifier, XGBRegressor

RANDOM_STATE = 42


@dataclass(frozen=True)
class TreeProfile:
    family: Literal["rf", "xgb", "lgbm"]
    name: str
    complexity: int
    parameters: dict[str, Any]

    @property
    def profile_id(self) -> str:
        return f"{self.family}-{self.name}"

    def regressor(self):
        if self.family == "rf":
            return RandomForestRegressor(**self.parameters)
        if self.family == "xgb":
            return XGBRegressor(**self.parameters, objective="reg:squarederror")
        return LGBMRegressor(**self.parameters, objective="regression")

    def classifier(self):
        if self.family == "rf":
            return RandomForestClassifier(**self.parameters, class_weight=None)
        if self.family == "xgb":
            return XGBClassifier(**self.parameters, objective="binary:logistic", eval_metric="logloss")
        return LGBMClassifier(**self.parameters, objective="binary", class_weight=None)


TREE_PROFILES = (
    TreeProfile("rf", "small", 0, {
        "n_estimators": 300, "max_depth": 4, "min_samples_leaf": 100,
        "max_features": "sqrt", "bootstrap": True, "random_state": RANDOM_STATE,
        "n_jobs": -1,
    }),
    TreeProfile("rf", "medium", 1, {
        "n_estimators": 400, "max_depth": 8, "min_samples_leaf": 50,
        "max_features": "sqrt", "bootstrap": True, "random_state": RANDOM_STATE,
        "n_jobs": -1,
    }),
    TreeProfile("rf", "wide", 2, {
        "n_estimators": 400, "max_depth": None, "min_samples_leaf": 100,
        "max_features": 0.5, "bootstrap": True, "random_state": RANDOM_STATE,
        "n_jobs": -1,
    }),
    TreeProfile("xgb", "small", 0, {
        "max_depth": 3, "learning_rate": 0.03, "n_estimators": 300,
        "min_child_weight": 20, "reg_lambda": 10, "reg_alpha": 0,
        "subsample": 0.8, "colsample_bytree": 0.8, "random_state": RANDOM_STATE,
        "n_jobs": -1, "tree_method": "hist",
    }),
    TreeProfile("xgb", "reg", 1, {
        "max_depth": 3, "learning_rate": 0.02, "n_estimators": 600,
        "min_child_weight": 50, "reg_lambda": 20, "reg_alpha": 1,
        "subsample": 0.8, "colsample_bytree": 0.8, "random_state": RANDOM_STATE,
        "n_jobs": -1, "tree_method": "hist",
    }),
    TreeProfile("xgb", "medium", 2, {
        "max_depth": 4, "learning_rate": 0.03, "n_estimators": 500,
        "min_child_weight": 20, "reg_lambda": 10, "reg_alpha": 0,
        "subsample": 0.8, "colsample_bytree": 0.8, "random_state": RANDOM_STATE,
        "n_jobs": -1, "tree_method": "hist",
    }),
    TreeProfile("lgbm", "small", 0, {
        "num_leaves": 15, "max_depth": 4, "learning_rate": 0.03,
        "n_estimators": 300, "min_child_samples": 100, "reg_lambda": 10,
        "reg_alpha": 0, "subsample": 0.8, "colsample_bytree": 0.8,
        "random_state": RANDOM_STATE, "n_jobs": -1, "verbosity": -1,
    }),
    TreeProfile("lgbm", "reg", 1, {
        "num_leaves": 15, "max_depth": 4, "learning_rate": 0.02,
        "n_estimators": 600, "min_child_samples": 150, "reg_lambda": 20,
        "reg_alpha": 1, "subsample": 0.8, "colsample_bytree": 0.8,
        "random_state": RANDOM_STATE, "n_jobs": -1, "verbosity": -1,
    }),
    TreeProfile("lgbm", "medium", 2, {
        "num_leaves": 31, "max_depth": 6, "learning_rate": 0.03,
        "n_estimators": 500, "min_child_samples": 75, "reg_lambda": 10,
        "reg_alpha": 0, "subsample": 0.8, "colsample_bytree": 0.8,
        "random_state": RANDOM_STATE, "n_jobs": -1, "verbosity": -1,
    }),
)

if len(TREE_PROFILES) != 9 or len({profile.profile_id for profile in TREE_PROFILES}) != 9:
    raise RuntimeError("Phase 3C requires exactly nine unique tree profiles")
