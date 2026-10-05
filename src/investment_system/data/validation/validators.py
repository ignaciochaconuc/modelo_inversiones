from datetime import datetime
from collections.abc import Iterable
from investment_system.core.time_utils import validate_available_at
from investment_system.data.schemas.base import PointInTimeRecord
from investment_system.data.schemas.features import FEATURE_COLUMNS, TARGET_COLUMNS

def validate_point_in_time(records: Iterable[PointInTimeRecord], decision_time: datetime) -> None:
    for record in records:
        validate_available_at(record.available_at, decision_time)

def validate_feature_target_separation() -> None:
    overlap = set(FEATURE_COLUMNS) & set(TARGET_COLUMNS)
    if overlap:
        raise ValueError(f"feature/target overlap: {sorted(overlap)}")
