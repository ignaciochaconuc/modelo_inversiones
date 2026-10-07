import numpy as np
import pandas as pd
import pytest

from investment_system.data.schemas.features import TARGET_COLUMNS
from investment_system.features.targets import TARGET_METADATA_COLUMNS
from investment_system.models.feature_sets import (
    FORBIDDEN_BASELINE_FEATURES,
    LOG1P_FEATURES,
    QUANTITATIVE_BASELINE_FEATURES,
    QUANTITATIVE_BASELINE_VERSION,
)
from investment_system.models.preprocessing import BaselinePreprocessor, PREPROCESSING_VERSION


def test_official_feature_set_is_exact_stable_and_contains_no_forbidden_data() -> None:
    assert QUANTITATIVE_BASELINE_VERSION == "quantitative-baseline-v1"
    assert PREPROCESSING_VERSION == "baseline-standard-v1"
    assert len(QUANTITATIVE_BASELINE_FEATURES) == 52
    assert QUANTITATIVE_BASELINE_FEATURES[0] == "return_1d"
    assert QUANTITATIVE_BASELINE_FEATURES[-1] == "percentile_volatility_252d"
    forbidden = {
        *FORBIDDEN_BASELINE_FEATURES, *TARGET_COLUMNS, *TARGET_METADATA_COLUMNS,
        "ticker", "sector", "industry", "decision_date", "decision_time",
    }
    assert not set(QUANTITATIVE_BASELINE_FEATURES) & forbidden
    assert LOG1P_FEATURES == ("avg_dollar_volume_20d", "avg_dollar_volume_60d")


def test_preprocessing_fits_medians_and_scaler_only_on_train_and_log_transforms_adv() -> None:
    train = pd.DataFrame({
        "return_1d": [1.0, np.nan, 3.0],
        "avg_dollar_volume_20d": [0.0, 9.0, 99.0],
    })
    validation = pd.DataFrame({
        "return_1d": [1000.0, np.nan],
        "avg_dollar_volume_20d": [9999.0, 9.0],
    })
    processor = BaselinePreprocessor(train.columns).fit(train)
    before = processor.metadata()
    transformed = processor.transform(validation)
    after = processor.metadata()
    assert before == after
    rows = {row["original_feature"]: row for row in before["features"]}
    assert rows["return_1d"]["train_median"] == 2.0
    assert rows["avg_dollar_volume_20d"]["train_median"] == pytest.approx(np.log1p(9.0))
    assert "avg_dollar_volume_20d" not in transformed
    assert "log_avg_dollar_volume_20d" in transformed
    assert transformed.iloc[1]["return_1d"] == pytest.approx(0.0)


def test_all_na_fails_and_constant_feature_is_audibly_excluded() -> None:
    with pytest.raises(ValueError, match="entirely NA"):
        BaselinePreprocessor(["return_1d"]).fit(pd.DataFrame({"return_1d": [np.nan, np.nan]}))
    processor = BaselinePreprocessor(["return_1d", "return_2d"]).fit(pd.DataFrame({
        "return_1d": [1.0, 1.0, np.nan], "return_2d": [1.0, 2.0, 3.0],
    }))
    assert processor.excluded_degenerate_features == ("return_1d",)
    assert processor.effective_feature_names == ("return_2d",)
    metadata = processor.metadata()
    excluded = [row for row in metadata["features"] if row["excluded_as_degenerate"]]
    assert [row["transformed_feature"] for row in excluded] == ["return_1d"]


def test_negative_liquidity_fails_explicitly() -> None:
    with pytest.raises(ValueError, match="negative"):
        BaselinePreprocessor(["avg_dollar_volume_20d"]).fit(
            pd.DataFrame({"avg_dollar_volume_20d": [-1.0, 1.0]})
        )
