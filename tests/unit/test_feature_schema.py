from datetime import date
from investment_system.data.schemas.features import FEATURE_COLUMNS, TARGET_COLUMNS, FeatureRow
from investment_system.data.validation.validators import validate_feature_target_separation

def test_features_and_targets_are_disjoint() -> None:
    validate_feature_target_separation()
    assert set(FEATURE_COLUMNS).isdisjoint(TARGET_COLUMNS)

def test_model_features_excludes_targets() -> None:
    row = FeatureRow(ticker="AAPL", decision_date=date(2025, 1, 2), return_10d=0.1, target_return_10d=0.2)
    values = row.model_features()
    assert values["return_10d"] == 0.1
    assert "target_return_10d" not in values
