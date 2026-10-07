"""Naive train-only predictive baselines."""
from __future__ import annotations

import numpy as np
import pandas as pd


class ZeroPredictor:
    def fit(self, _: pd.DataFrame, __: pd.Series) -> "ZeroPredictor":
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        return np.zeros(len(features), dtype=float)


class TrainMeanPredictor:
    def __init__(self) -> None:
        self.mean_: float | None = None

    def fit(self, _: pd.DataFrame, target: pd.Series) -> "TrainMeanPredictor":
        self.mean_ = float(target.mean())
        return self

    def predict(self, features: pd.DataFrame) -> np.ndarray:
        if self.mean_ is None:
            raise ValueError("predictor must be fitted on TRAIN")
        return np.full(len(features), self.mean_, dtype=float)


class TrainPriorPredictor:
    def __init__(self) -> None:
        self.prior_: float | None = None

    def fit(self, _: pd.DataFrame, target: pd.Series) -> "TrainPriorPredictor":
        self.prior_ = float(target.mean())
        if not 0 < self.prior_ < 1:
            raise ValueError("TRAIN classification target must contain both classes")
        return self

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        if self.prior_ is None:
            raise ValueError("predictor must be fitted on TRAIN")
        positive = np.full(len(features), self.prior_, dtype=float)
        return np.column_stack([1 - positive, positive])
