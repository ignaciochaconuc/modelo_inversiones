from abc import ABC, abstractmethod
from typing import Any
import pandas as pd

class BasePredictiveModel(ABC):
    model_version: str
    target_name: str
    @abstractmethod
    def fit(self, features: pd.DataFrame, target: pd.Series) -> "BasePredictiveModel": ...
    @abstractmethod
    def predict(self, features: pd.DataFrame) -> Any: ...
