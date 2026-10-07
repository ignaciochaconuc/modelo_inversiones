"""Train-only deterministic preprocessing for Phase 3B baselines."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from sklearn.preprocessing import StandardScaler

from investment_system.models.feature_sets import LOG1P_FEATURES

PREPROCESSING_VERSION = "baseline-standard-v1"


@dataclass(frozen=True)
class PreprocessedData:
    values: pd.DataFrame


class BaselinePreprocessor:
    """Apply log liquidity transforms, train medians, and train scaling only."""

    def __init__(self, feature_names: Sequence[str]) -> None:
        self.original_feature_names = tuple(feature_names)
        self.imputer: SimpleImputer | None = None
        self.scaler: StandardScaler | None = None
        self.transformed_feature_names: tuple[str, ...] = ()
        self.effective_feature_names: tuple[str, ...] = ()
        self.excluded_degenerate_features: tuple[str, ...] = ()
        self._effective_indices: tuple[int, ...] = ()

    @staticmethod
    def _transformed_name(name: str) -> str:
        return f"log_{name}" if name in LOG1P_FEATURES else name

    def _deterministic_transforms(self, frame: pd.DataFrame) -> pd.DataFrame:
        if tuple(frame.columns) != self.original_feature_names:
            raise ValueError("feature columns/order differ from the configured feature set")
        transformed = frame.astype(float).copy()
        for name in LOG1P_FEATURES:
            if name not in transformed:
                continue
            valid = transformed[name].dropna()
            if (valid < 0).any():
                raise ValueError(f"{name} contains negative values and cannot use log1p")
            transformed[name] = np.log1p(transformed[name])
        transformed.columns = [self._transformed_name(name) for name in transformed.columns]
        return transformed

    def fit(self, train: pd.DataFrame) -> "BaselinePreprocessor":
        transformed = self._deterministic_transforms(train)
        all_nan = transformed.columns[transformed.isna().all()].tolist()
        if all_nan:
            raise ValueError(f"features are entirely NA in TRAIN: {all_nan}")
        self.transformed_feature_names = tuple(transformed.columns)
        self.imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        imputed = self.imputer.fit_transform(transformed)
        variances = np.var(imputed, axis=0)
        effective_indices = np.flatnonzero(variances > 0)
        excluded_indices = np.flatnonzero(variances == 0)
        self._effective_indices = tuple(int(value) for value in effective_indices)
        self.effective_feature_names = tuple(
            self.transformed_feature_names[index] for index in self._effective_indices
        )
        self.excluded_degenerate_features = tuple(
            self.transformed_feature_names[int(index)] for index in excluded_indices
        )
        if not self.effective_feature_names:
            raise ValueError("all TRAIN features are degenerate after imputation")
        self.scaler = StandardScaler()
        self.scaler.fit(imputed[:, self._effective_indices])
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self.imputer is None or self.scaler is None:
            raise ValueError("preprocessor must be fitted on TRAIN before transform")
        transformed = self._deterministic_transforms(frame)
        imputed = self.imputer.transform(transformed)
        scaled = self.scaler.transform(imputed[:, self._effective_indices])
        return pd.DataFrame(scaled, columns=self.effective_feature_names, index=frame.index)

    def fit_transform(self, train: pd.DataFrame) -> pd.DataFrame:
        return self.fit(train).transform(train)

    def metadata(self) -> dict[str, Any]:
        if self.imputer is None or self.scaler is None:
            raise ValueError("preprocessor has not been fitted")
        effective_position = {index: position for position, index in enumerate(self._effective_indices)}
        rows = []
        for index, (original, transformed) in enumerate(
            zip(self.original_feature_names, self.transformed_feature_names)
        ):
            position = effective_position.get(index)
            rows.append({
                "original_feature": original,
                "transformed_feature": transformed,
                "transformation": "log1p" if original in LOG1P_FEATURES else "identity",
                "train_median": float(self.imputer.statistics_[index]),
                "scaler_mean": float(self.scaler.mean_[position]) if position is not None else None,
                "scaler_std": float(self.scaler.scale_[position]) if position is not None else None,
                "excluded_as_degenerate": position is None,
            })
        return {
            "preprocessing_version": PREPROCESSING_VERSION,
            "fit_partition": "train",
            "features": rows,
        }
