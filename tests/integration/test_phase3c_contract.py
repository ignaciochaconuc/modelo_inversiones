from datetime import date
from types import SimpleNamespace

import numpy as np
import pandas as pd

import investment_system.models.phase3c as phase3c
from investment_system.models.phase3b import SelectionDataset
from investment_system.models.phase3c import NonlinearResult, Phase3CSelectionRunner
from investment_system.models.supervised import SupervisedPartition


class _FixedModel:
    feature_importances_ = np.array([.25, .75])

    def predict(self, x):
        return np.asarray(x["a"], dtype=float)


def test_phase3c_contract_has_no_test_and_importance_receives_validation_only(tmp_path, monkeypatch) -> None:
    train = SupervisedPartition(pd.DataFrame({"a": [1.0], "b": [2.0]}), pd.Series([0.0]), pd.DataFrame())
    validation = SupervisedPartition(pd.DataFrame({"a": [3.0], "b": [4.0]}), pd.Series([1.0]), pd.DataFrame())
    selection = SelectionDataset(train, validation, {})
    assert not hasattr(selection, "test")
    seen = {}

    def fake_permutation(model, x, y, **kwargs):
        seen["index"] = x.index.tolist()
        seen["rows"] = len(x)
        seen["repeats"] = kwargs["n_repeats"]
        return SimpleNamespace(importances_mean=np.array([.1, .2]), importances_std=np.array([.01, .02]))

    monkeypatch.setattr(phase3c, "permutation_importance", fake_permutation)
    x_validation = pd.DataFrame({"a": [10.0, 20.0], "b": [30.0, 40.0]}, index=[100, 101])
    metadata = pd.DataFrame({"decision_date": [date(2019, 1, 2), date(2020, 1, 2)]})
    result = NonlinearResult(
        "rf-small-regression-5d-qbaselinev1-treeprepv1", "rf", "small", 0,
        "regression", "model", 5, {}, {}, pd.DataFrame(), {}, True,
        model=_FixedModel(), validation_x=x_validation, validation_y=pd.Series([1.0, 2.0]),
        validation_metadata=metadata,
    )
    runner = Phase3CSelectionRunner(tmp_path, feature_schema_version="4", target_schema_version="v3")
    before = result.model.predict(x_validation).copy()
    destination = runner.persist_feature_importance(result)
    after = result.model.predict(x_validation)
    assert seen == {"index": [100, 101], "rows": 2, "repeats": phase3c.PERMUTATION_REPEATS}
    np.testing.assert_array_equal(before, after)
    assert destination.exists()
    assert not any("test" in path.name.lower() for path in tmp_path.rglob("*"))
