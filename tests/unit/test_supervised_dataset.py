from datetime import date

import pandas as pd
import pytest

from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.models.contracts import TargetSpec
from investment_system.models.supervised import SupervisedDatasetBuilder, TemporalSplitSpec


def _inputs() -> tuple[pd.DataFrame, pd.DataFrame]:
    dates_and_ends = [
        (date(2018, 12, 27), date(2018, 12, 31)),
        (date(2018, 12, 28), date(2019, 1, 2)),
        (date(2018, 12, 31), date(2019, 1, 3)),
        (date(2019, 1, 2), date(2019, 1, 9)),
        (date(2021, 12, 30), date(2022, 1, 3)),
        (date(2022, 1, 3), date(2022, 1, 10)),
        (date(2022, 1, 4), date(2022, 1, 11)),
    ]
    rows = [(ticker, decision, end) for decision, end in dates_and_ends for ticker in ("A", "B")]
    features = pd.DataFrame({
        "ticker": [row[0] for row in rows],
        "decision_date": [row[1] for row in rows],
        "model_eligible": True,
        "feature_corporate_action_contaminated": False,
        "return_1d": range(len(rows)),
        # An unselected target-like payload must never leak through the allowlist.
        "target_return_20d": 999.0,
    })
    targets = pd.DataFrame({
        "ticker": [row[0] for row in rows],
        "decision_date": [row[1] for row in rows],
        "target_return_5d": 0.01,
        "target_5d_training_eligible": True,
        "target_end_date_5d": [row[2] for row in rows],
    })
    return features, targets


def _builder() -> SupervisedDatasetBuilder:
    return SupervisedDatasetBuilder(XNYSTradingCalendar(), feature_schema_version="4")


def test_fixed_split_is_by_complete_date_and_purges_boundary_equality(tmp_path) -> None:
    features, targets = _inputs()
    dataset = _builder().build(
        features, targets, TargetSpec(task="regression", horizon=5),
        feature_columns=["return_1d"],
    )
    train_dates = set(dataset.train.metadata["decision_date"])
    validation_dates = set(dataset.validation.metadata["decision_date"])
    test_dates = set(dataset.test.metadata["decision_date"])
    assert train_dates == {date(2018, 12, 27)}
    assert validation_dates == {date(2019, 1, 2)}
    assert test_dates == {date(2022, 1, 3), date(2022, 1, 4)}
    assert dataset.train.metadata.groupby("decision_date")["ticker"].nunique().eq(2).all()
    assert dataset.validation.metadata.groupby("decision_date")["ticker"].nunique().eq(2).all()
    assert list(dataset.train.X) == ["return_1d"]
    assert not any(column.startswith("target_") for column in dataset.train.X)
    assert dataset.manifest["purge_rule"] == "target_end_date < next_split_start"
    assert dataset.write_manifest(tmp_path / "supervised_manifest.json").exists()


def test_target_eligibility_controls_test_and_ranking_na_is_excluded() -> None:
    features, targets = _inputs()
    mask = (targets["ticker"] == "A") & (targets["decision_date"] == date(2022, 1, 3))
    targets.loc[mask, "target_5d_training_eligible"] = False
    dataset = _builder().build(
        features, targets, TargetSpec(task="regression", horizon=5),
        feature_columns=["return_1d"],
    )
    assert not ((dataset.test.metadata["ticker"] == "A") &
                (dataset.test.metadata["decision_date"] == date(2022, 1, 3))).any()

    targets = targets.rename(columns={"target_return_5d": "target_rank_5d"})
    targets.loc[targets["ticker"] == "B", "target_rank_5d"] = float("nan")
    ranked = _builder().build(
        features, targets, TargetSpec(task="ranking", horizon=5),
        feature_columns=["return_1d"],
    )
    assert set(ranked.test.metadata["ticker"]) <= {"A"}


def test_embargo_uses_xnys_sessions_and_zero_changes_nothing() -> None:
    features, targets = _inputs()
    base = _builder().build(
        features, targets, TargetSpec(task="regression", horizon=5),
        feature_columns=["return_1d"],
    )
    zero = _builder().build(
        features, targets, TargetSpec(task="regression", horizon=5),
        TemporalSplitSpec(embargo_sessions=0), feature_columns=["return_1d"],
    )
    assert base.manifest["row_counts"]["final"] == zero.manifest["row_counts"]["final"]
    embargoed = _builder().build(
        features, targets, TargetSpec(task="regression", horizon=5),
        TemporalSplitSpec(embargo_sessions=1), feature_columns=["return_1d"],
    )
    assert date(2019, 1, 2) not in set(embargoed.validation.metadata["decision_date"])
    assert date(2022, 1, 3) not in set(embargoed.test.metadata["decision_date"])
    assert date(2022, 1, 4) in set(embargoed.test.metadata["decision_date"])
    assert embargoed.manifest["row_counts"]["after_purging"] == base.manifest["row_counts"]["after_purging"]


def test_real_target_end_dates_make_horizon_purging_different() -> None:
    features, targets = _inputs()
    targets["target_return_20d"] = 0.02
    targets["target_20d_training_eligible"] = True
    targets["target_end_date_20d"] = targets["target_end_date_5d"]
    near_boundary = targets["decision_date"] == date(2018, 12, 27)
    targets.loc[near_boundary, "target_end_date_20d"] = date(2019, 1, 10)
    five = _builder().build(features, targets, TargetSpec(task="regression", horizon=5), feature_columns=["return_1d"])
    twenty = _builder().build(features, targets, TargetSpec(task="regression", horizon=20), feature_columns=["return_1d"])
    assert len(five.train.y) == 2
    assert twenty.train.y.empty


def test_duplicate_keys_and_invalid_feature_selection_fail_explicitly() -> None:
    features, targets = _inputs()
    with pytest.raises(ValueError, match="duplicate"):
        _builder().build(pd.concat([features, features.iloc[[0]]]), targets,
                         TargetSpec(task="regression", horizon=5), feature_columns=["return_1d"])
    with pytest.raises(ValueError, match="duplicate"):
        _builder().build(features, pd.concat([targets, targets.iloc[[0]]]),
                         TargetSpec(task="regression", horizon=5), feature_columns=["return_1d"])
    with pytest.raises(ValueError, match="not registered"):
        _builder().build(features, targets, TargetSpec(task="regression", horizon=5),
                         feature_columns=["target_return_20d"])
    with pytest.raises(ValueError, match="not registered"):
        _builder().build(features, targets, TargetSpec(task="regression", horizon=5),
                         feature_columns=["target_end_date_5d"])
