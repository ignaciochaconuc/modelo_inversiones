from datetime import date

import numpy as np
import pandas as pd
import pytest

from investment_system.models.feature_ablations import (
    ABLATION_MATERIAL_THRESHOLD,
    ABLATION_NEUTRAL_TOLERANCE,
    ABLATION_POLICIES,
    EXPECTED_FEATURE_COUNTS,
    FEATURE_FAMILIES,
    ablation_policy_features,
    classify_ablation,
    diagnostic_flags,
    validate_family_contract,
)
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.tree_preprocessing import TreePreprocessor
from investment_system.models.walkforward import Phase3DWalkForwardRunner
from investment_system.models.window_sensitivity import window_training_masks


def test_feature_families_are_an_exact_disjoint_partition() -> None:
    validate_family_contract()
    flattened = [feature for family in FEATURE_FAMILIES.values() for feature in family]
    assert len(FEATURE_FAMILIES) == 10
    assert len(flattened) == len(set(flattened)) == 52
    assert set(flattened) == set(QUANTITATIVE_BASELINE_FEATURES)
    assert {name: len(values) for name, values in FEATURE_FAMILIES.items()} == {
        "returns": 9, "momentum": 5, "relative_momentum": 3, "volatility": 6,
        "trend": 8, "liquidity_volume": 5, "drawdown": 2, "market": 5,
        "relative_risk": 4, "historical_position": 5,
    }


def test_ablation_subsets_remove_exactly_one_family_in_canonical_order() -> None:
    assert len(ABLATION_POLICIES) == 11
    assert ablation_policy_features("full") == tuple(QUANTITATIVE_BASELINE_FEATURES)
    for policy in ABLATION_POLICIES:
        subset = ablation_policy_features(policy)
        assert len(subset) == EXPECTED_FEATURE_COUNTS[policy]
        assert subset == tuple(feature for feature in QUANTITATIVE_BASELINE_FEATURES if feature in subset)
        if policy != "full":
            family = policy.removeprefix("without_")
            assert set(QUANTITATIVE_BASELINE_FEATURES) - set(subset) == set(FEATURE_FAMILIES[family])


def test_tree_preprocessing_accepts_liquidity_ablation_without_recreating_adv() -> None:
    features = ablation_policy_features("without_liquidity_volume")
    train = pd.DataFrame({
        feature: [float(index), np.nan, float(index + 2)]
        for index, feature in enumerate(features)
    })
    preprocessor = TreePreprocessor(features)
    transformed = preprocessor.fit_transform(train)
    assert "avg_dollar_volume_20d" not in preprocessor.original_feature_names
    assert "avg_dollar_volume_60d" not in preprocessor.original_feature_names
    assert not any("avg_dollar_volume" in column for column in transformed.columns)
    assert preprocessor.metadata()["scaling"] is None
    assert len(transformed.columns) == len(features)
    expected_median = float(np.median([0.0, 2.0]))
    assert transformed.iloc[1, 0] == expected_median


def test_full_preprocessing_log_transforms_only_present_adv_columns() -> None:
    features = ablation_policy_features("full")
    train = pd.DataFrame({feature: [1.0, 2.0, 4.0] for feature in features})
    preprocessor = TreePreprocessor(features).fit(train)
    metadata = {row["original_feature"]: row for row in preprocessor.metadata()["features"]}
    assert metadata["avg_dollar_volume_20d"]["transformation"] == "log1p"
    assert metadata["avg_dollar_volume_60d"]["transformation"] == "log1p"
    assert metadata["return_1d"]["transformation"] == "identity"


@pytest.mark.parametrize(("delta", "expected"), [
    (-0.005, "important"),
    (-0.004, "moderately_useful"),
    (-0.003, "moderately_useful"),
    (0.0, "neutral_or_redundant"),
    (0.002999, "neutral_or_redundant"),
    (0.003, "small_positive_change"),
    (0.004, "small_positive_change"),
    (0.005, "potentially_harmful"),
])
def test_ablation_classification_boundaries_are_gap_free(delta, expected) -> None:
    assert classify_ablation(delta) == expected


def test_harmful_candidate_requires_all_stability_conditions() -> None:
    assert ABLATION_NEUTRAL_TOLERANCE == 0.003
    assert ABLATION_MATERIAL_THRESHOLD == 0.005
    passing = dict(
        delta_mean_ic=0.005, delta_worst_year_ic=-0.003,
        delta_icir=-0.02, delta_top10_uplift=-0.001,
    )
    assert diagnostic_flags(**passing)["harmful_candidate"] is True
    for name, failed_value in (
        ("delta_mean_ic", 0.004999),
        ("delta_worst_year_ic", -0.003001),
        ("delta_icir", -0.020001),
        ("delta_top10_uplift", -0.001001),
    ):
        values = {**passing, name: failed_value}
        assert diagnostic_flags(**values)["harmful_candidate"] is False


def test_strong_contributor_accepts_mean_or_stability_contribution() -> None:
    common = {"delta_icir": 0.0, "delta_top10_uplift": 0.0}
    assert diagnostic_flags(
        delta_mean_ic=-0.005, delta_worst_year_ic=0.0, **common,
    )["strong_contributor"] is True
    assert diagnostic_flags(
        delta_mean_ic=0.0, delta_worst_year_ic=-0.005, **common,
    )["strong_contributor"] is True
    assert diagnostic_flags(
        delta_mean_ic=-0.004999, delta_worst_year_ic=-0.004999, **common,
    )["strong_contributor"] is False


def test_frozen_dimensions_and_strict_expanding_purge() -> None:
    factory, preprocessor, version, parameters = Phase3DWalkForwardRunner._model_factory("rf-small")
    assert parameters == {
        "n_estimators": 300, "max_depth": 4, "min_samples_leaf": 100,
        "max_features": "sqrt", "bootstrap": True, "random_state": 42, "n_jobs": -1,
    }
    assert preprocessor is TreePreprocessor
    assert version == "tree-preprocessing-v1"
    assert factory().get_params()["random_state"] == 42
    frame = pd.DataFrame({
        "decision_date": [date(2010, 1, 4), date(2015, 12, 1), date(2015, 12, 2)],
        "target_end_date_20d": [date(2010, 2, 2), date(2015, 12, 31), date(2016, 1, 4)],
    })
    _, purged, start, _ = window_training_masks(frame, date(2016, 1, 4), "expanding")
    assert start == date(2010, 1, 4)
    assert frame.loc[purged, "target_end_date_20d"].max() < date(2016, 1, 4)
