from datetime import date

import numpy as np
import pandas as pd

from investment_system.models.contracts import TargetSpec
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.phase3b import Phase3BSelectionRunner, SelectionDataset
from investment_system.models.supervised import SupervisedPartition


def _x(rows: int) -> pd.DataFrame:
    values = {}
    for index, name in enumerate(QUANTITATIVE_BASELINE_FEATURES):
        if name.startswith("avg_dollar_volume"):
            values[name] = np.arange(rows, dtype=float) + index + 1
        else:
            values[name] = np.arange(rows, dtype=float) * (index + 1) / 100 + index
    return pd.DataFrame(values)


def _selection(target: str) -> SelectionDataset:
    train_dates = [date(2018, 12, 1)] * 6 + [date(2018, 12, 2)] * 6
    validation_dates = (
        [date(2019, 1, 2)] * 4 + [date(2020, 1, 2)] * 4 + [date(2021, 1, 4)] * 4
    )
    train_meta = pd.DataFrame({"ticker": list("ABCDEFGHIJKL"), "decision_date": train_dates})
    validation_meta = pd.DataFrame({"ticker": list("ABCDEFGHIJKL"), "decision_date": validation_dates})
    if target == "classification":
        train_y = pd.Series([0, 1] * 6)
        validation_y = pd.Series([0, 1] * 6)
    elif target == "ranking":
        train_y = pd.Series(np.tile(np.linspace(0, 1, 6), 2))
        validation_y = pd.Series(np.tile(np.linspace(0, 1, 4), 3))
    else:
        train_y = pd.Series(np.linspace(-.1, .1, 12))
        validation_y = pd.Series(np.linspace(-.08, .12, 12))
    manifest = {
        "dates": {"train": ["2010-01-04", "2018-12-31"],
                  "validation": ["2019-01-02", "2021-12-31"]},
        "purge_rule_version": "target-end-date-strict-v1", "embargo_sessions": 0,
    }
    return SelectionDataset(
        SupervisedPartition(_x(12), train_y, train_meta),
        SupervisedPartition(_x(12) + .01, validation_y, validation_meta),
        manifest,
    )


def test_runner_executes_all_simple_families_and_persists_validation_only(tmp_path) -> None:
    runner = Phase3BSelectionRunner(
        tmp_path, feature_schema_version="4", target_schema_version="v3"
    )
    regression_data = _selection("regression")
    regression = runner.run_regression(
        regression_data, TargetSpec(task="regression", horizon=10)
    )
    classification = runner.run_classification(
        _selection("classification"), TargetSpec(task="classification", horizon=10)
    )
    ranking_data = _selection("ranking")
    ranking = runner.run_ranking(
        ranking_data, TargetSpec(task="ranking", horizon=10),
        pd.Series(np.linspace(-.1, .1, 12)), pd.Series(np.linspace(-.08, .12, 12)),
        regression,
    )
    selected = {
        regression["best_ridge"].experiment_id,
        classification["best_logistic"].experiment_id,
        ranking["best_approach"].experiment_id,
    }
    summary = runner.persist_experiments(selected)
    assert len(summary) == 23
    assert summary["test_used"].eq(False).all()
    assert not any("test" in path.name for path in tmp_path.rglob("*.parquet"))
    assert (tmp_path / "summary.csv").exists()
    for experiment_id in summary["experiment_id"]:
        predictions = pd.read_parquet(tmp_path / experiment_id / "validation_predictions.parquet")
        assert pd.to_datetime(predictions["decision_date"]).dt.year.max() == 2021
