from datetime import date, datetime, timezone

import pytest
from pydantic import ValidationError

from investment_system.models.contracts import OutOfSamplePrediction


def _prediction(**updates):
    values = {
        "ticker": "AAPL",
        "decision_date": date(2022, 1, 3),
        "prediction": 0.02,
        "task": "regression",
        "target_name": "target_return_10d",
        "horizon": 10,
        "model_id": "baseline-v1",
        "training_cutoff": date(2021, 12, 31),
        "split": "test",
        "generated_at": datetime(2022, 1, 3, 22, tzinfo=timezone.utc),
        "is_out_of_sample": True,
    }
    values.update(updates)
    return OutOfSamplePrediction.model_validate(values)


def test_prediction_identifies_target_model_and_training_cutoff() -> None:
    prediction = _prediction()
    assert prediction.target_name == "target_return_10d"
    assert prediction.model_id == "baseline-v1"
    assert prediction.training_cutoff < prediction.decision_date
    assert not ({"weight", "order", "execution"} & set(type(prediction).model_fields))


def test_prediction_rejects_missing_mismatch_and_non_oos_values() -> None:
    payload = _prediction().model_dump()
    del payload["model_id"]
    with pytest.raises(ValidationError):
        OutOfSamplePrediction.model_validate(payload)
    with pytest.raises(ValidationError):
        _prediction(target_name="target_positive_10d")
    with pytest.raises(ValidationError):
        _prediction(training_cutoff=date(2022, 1, 3))
    with pytest.raises(ValidationError):
        _prediction(is_out_of_sample=False)
