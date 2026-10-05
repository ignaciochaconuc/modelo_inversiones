import numpy as np
import pandas as pd

from investment_system.data.schemas.features import TARGET_COLUMNS

def validate_quantitative_feature_frame(frame: pd.DataFrame) -> None:
    if frame.duplicated(["ticker", "decision_date"]).any():
        raise ValueError("duplicate ticker + decision_date in feature dataset")
    raw_times = frame["decision_time"]
    if any(getattr(value, "tzinfo", None) is None or value.utcoffset() is None for value in raw_times):
        raise ValueError("decision_time must be timezone-aware and valid")
    times = pd.to_datetime(raw_times, utc=True, errors="coerce")
    if times.isna().any():
        raise ValueError("decision_time must be timezone-aware and valid")
    if set(TARGET_COLUMNS) & set(frame.columns):
        raise ValueError("target columns are forbidden in the feature dataset")
    numeric = frame.select_dtypes(include=[np.number])
    if np.isinf(numeric.to_numpy()).any():
        raise ValueError("feature dataset contains infinity")

def validate_target_frame(frame: pd.DataFrame) -> None:
    if frame.duplicated(["ticker", "decision_date"]).any():
        raise ValueError("duplicate ticker + decision_date in target dataset")
    forbidden = set(frame.columns) - {"ticker", "decision_date", *TARGET_COLUMNS}
    if forbidden:
        raise ValueError(f"unexpected columns in target dataset: {sorted(forbidden)}")
