"""Train-only preprocessing for tree models, deliberately without scaling."""
from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer

from investment_system.models.feature_sets import LOG1P_FEATURES

TREE_PREPROCESSING_VERSION = "tree-preprocessing-v1"


class TreePreprocessor:
    """Apply deterministic transforms and TRAIN medians, but never scale."""

    def __init__(self, feature_names: Sequence[str]) -> None:
        self.original_feature_names = tuple(feature_names)
        self.transformed_feature_names: tuple[str, ...] = ()
        self.effective_feature_names: tuple[str, ...] = ()
        self.excluded_degenerate_features: tuple[str, ...] = ()
        self.imputer: SimpleImputer | None = None
        self._effective_indices: tuple[int, ...] = ()

    @staticmethod
    def _name(name: str) -> str:
        return f"log_{name}" if name in LOG1P_FEATURES else name

    def _transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if tuple(frame.columns) != self.original_feature_names:
            raise ValueError("feature columns/order differ from quantitative-baseline-v1")
        result = frame.astype(float).copy()
        for name in LOG1P_FEATURES:
            if name not in result:
                continue
            valid = result[name].dropna()
            if (valid < 0).any():
                raise ValueError(f"{name} contains negative values and cannot use log1p")
            result[name] = np.log1p(result[name])
        result.columns = [self._name(name) for name in result.columns]
        return result

    def fit(self, train: pd.DataFrame) -> "TreePreprocessor":
        transformed = self._transform(train)
        all_nan = transformed.columns[transformed.isna().all()].tolist()
        if all_nan:
            raise ValueError(f"features are entirely NA in TRAIN: {all_nan}")
        self.transformed_feature_names = tuple(transformed.columns)
        self.imputer = SimpleImputer(strategy="median", keep_empty_features=True)
        imputed = self.imputer.fit_transform(transformed)
        variance = np.var(imputed, axis=0)
        self._effective_indices = tuple(int(value) for value in np.flatnonzero(variance > 0))
        excluded = tuple(int(value) for value in np.flatnonzero(variance == 0))
        self.effective_feature_names = tuple(
            self.transformed_feature_names[index] for index in self._effective_indices
        )
        self.excluded_degenerate_features = tuple(
            self.transformed_feature_names[index] for index in excluded
        )
        if not self.effective_feature_names:
            raise ValueError("all TRAIN features are degenerate after imputation")
        return self

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if self.imputer is None:
            raise ValueError("preprocessor must be fitted on TRAIN before transform")
        imputed = self.imputer.transform(self._transform(frame))
        return pd.DataFrame(
            imputed[:, self._effective_indices], columns=self.effective_feature_names,
            index=frame.index,
        )

    def fit_transform(self, train: pd.DataFrame) -> pd.DataFrame:
        return self.fit(train).transform(train)

    def metadata(self) -> dict[str, Any]:
        if self.imputer is None:
            raise ValueError("preprocessor has not been fitted")
        effective = set(self._effective_indices)
        return {
            "preprocessing_version": TREE_PREPROCESSING_VERSION,
            "fit_partition": "train",
            "scaling": None,
            "features": [
                {
                    "original_feature": original,
                    "transformed_feature": transformed,
                    "transformation": "log1p" if original in LOG1P_FEATURES else "identity",
                    "train_median": float(self.imputer.statistics_[index]),
                    "excluded_as_degenerate": index not in effective,
                }
                for index, (original, transformed) in enumerate(
                    zip(self.original_feature_names, self.transformed_feature_names)
                )
            ],
        }
