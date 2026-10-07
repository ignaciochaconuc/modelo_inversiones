import numpy as np
import pandas as pd
import pytest

from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.tree_preprocessing import TREE_PREPROCESSING_VERSION, TreePreprocessor


def test_tree_preprocessing_contract_is_exact_52_features_and_no_scaling() -> None:
    assert len(QUANTITATIVE_BASELINE_FEATURES) == 52
    assert TREE_PREPROCESSING_VERSION == "tree-preprocessing-v1"
    values = {name: [float(i + 1), float(i + 2), float(i + 3)] for i, name in enumerate(QUANTITATIVE_BASELINE_FEATURES)}
    processor = TreePreprocessor(QUANTITATIVE_BASELINE_FEATURES).fit(pd.DataFrame(values))
    metadata = processor.metadata()
    assert metadata["scaling"] is None
    assert [row["original_feature"] for row in metadata["features"]] == list(QUANTITATIVE_BASELINE_FEATURES)


def test_log1p_train_median_and_stable_order_do_not_learn_from_validation() -> None:
    train = pd.DataFrame({
        "return_1d": [1.0, np.nan, 3.0],
        "avg_dollar_volume_20d": [0.0, 9.0, 99.0],
    })
    validation = pd.DataFrame({
        "return_1d": [1000.0, np.nan],
        "avg_dollar_volume_20d": [9999.0, 9.0],
    })
    processor = TreePreprocessor(train.columns).fit(train)
    before = processor.metadata()
    transformed = processor.transform(validation)
    assert processor.metadata() == before
    assert transformed.columns.tolist() == ["return_1d", "log_avg_dollar_volume_20d"]
    assert transformed.iloc[1, 0] == pytest.approx(2.0)
    assert transformed.iloc[1, 1] == pytest.approx(np.log1p(9.0))
    assert before["features"][1]["train_median"] == pytest.approx(np.log1p(9.0))
    with pytest.raises(ValueError, match="columns/order"):
        processor.transform(validation[["avg_dollar_volume_20d", "return_1d"]])


def test_tree_preprocessing_fails_all_na_and_records_zero_variance() -> None:
    with pytest.raises(ValueError, match="entirely NA"):
        TreePreprocessor(["return_1d"]).fit(pd.DataFrame({"return_1d": [np.nan, np.nan]}))
    processor = TreePreprocessor(["return_1d", "return_2d"]).fit(pd.DataFrame({
        "return_1d": [1.0, 1.0, np.nan], "return_2d": [1.0, 2.0, 3.0],
    }))
    assert processor.excluded_degenerate_features == ("return_1d",)
    assert processor.effective_feature_names == ("return_2d",)

