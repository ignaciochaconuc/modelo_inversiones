from datetime import date, datetime, timezone
import pytest
from pydantic import ValidationError
from investment_system.data.schemas.features import FEATURE_COLUMNS, TARGET_COLUMNS, FeatureRow
from investment_system.data.validation.validators import validate_feature_target_separation

def test_features_and_targets_are_disjoint() -> None:
    validate_feature_target_separation()
    assert set(FEATURE_COLUMNS).isdisjoint(TARGET_COLUMNS)
    assert "split_adjusted_close" in FEATURE_COLUMNS
    assert "adjusted_close" not in FEATURE_COLUMNS

def test_model_features_excludes_targets() -> None:
    row = FeatureRow(ticker="AAPL", decision_date=date(2025, 1, 2), decision_time=datetime(2025, 1, 3, tzinfo=timezone.utc), return_10d=0.1, target_return_10d=0.2)
    values = row.model_features()
    assert values["return_10d"] == 0.1
    assert "target_return_10d" not in values

def test_decision_time_requires_timezone() -> None:
    with pytest.raises(ValidationError, match="timezone-aware"):
        FeatureRow(ticker="AAPL", decision_date=date(2025, 1, 2), decision_time=datetime(2025, 1, 2, 20, 15))
