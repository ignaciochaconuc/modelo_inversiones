from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.walkforward import (
    INITIAL_TRAIN_START,
    Phase3DWalkForwardRunner,
)
from investment_system.models.window_sensitivity import Phase3DWindowSensitivityRunner


def _synthetic_frame() -> pd.DataFrame:
    calendar = XNYSTradingCalendar()
    training_dates = []
    current = INITIAL_TRAIN_START
    for _ in range(18):
        if not calendar.is_session(current):
            current = calendar.next_session(current)
        training_dates.append(current)
        current = calendar.next_session(current + timedelta(days=100))
    prediction_dates = [date(year, 1, 4) for year in range(2016, 2022)]
    prediction_dates = [value if calendar.is_session(value) else calendar.next_session(value) for value in prediction_dates]
    rows = []
    for date_index, decision_date in enumerate([*training_dates, *prediction_dates]):
        for ticker_index in range(30):
            values = {}
            for feature_index, feature in enumerate(QUANTITATIVE_BASELINE_FEATURES):
                base = 1000.0 if feature.startswith("avg_dollar_volume") else 0.0
                values[feature] = base + ticker_index * (feature_index + 1) / 100 + date_index / 50
            actual = (ticker_index - 15) / 1000 + date_index / 10000
            rows.append({
                "ticker": f"T{ticker_index:02d}", "decision_date": decision_date,
                "target_return_20d": actual, "target_rank_20d": ticker_index / 29,
                "target_end_date_20d": decision_date + timedelta(days=30), **values,
            })
    return pd.DataFrame(rows).sort_values(["decision_date", "ticker"]).reset_index(drop=True)


def test_repeated_ridge_walkforward_is_deterministic_and_validation_only(tmp_path) -> None:
    frame = _synthetic_frame()
    runner = Phase3DWalkForwardRunner(
        tmp_path, XNYSTradingCalendar(), feature_schema_version="4", target_schema_version="v3"
    )
    first_predictions, first_fits, _, first_metrics = runner.run_policy(frame, "ridge-100", "annual")
    second_predictions, second_fits, _, second_metrics = runner.run_policy(frame, "ridge-100", "annual")
    np.testing.assert_allclose(first_predictions["predicted_return"], second_predictions["predicted_return"])
    assert first_metrics["overall"] == second_metrics["overall"]
    assert first_fits[["fit_id", "prediction_start", "prediction_end"]].equals(
        second_fits[["fit_id", "prediction_start", "prediction_end"]]
    )
    assert first_predictions["decision_date"].min().year == 2016
    assert first_predictions["decision_date"].max().year == 2021
    assert first_predictions["test_used"].eq(False).all()
    assert not first_predictions.duplicated(["ticker", "decision_date"]).any()
    assert set(first_predictions["fit_id"]) <= set(first_fits["fit_id"])
    assert (
        pd.to_datetime(first_predictions["decision_date"])
        >= pd.to_datetime(first_predictions["prediction_period_start"])
    ).all()
    assert (
        pd.to_datetime(first_predictions["decision_date"])
        <= pd.to_datetime(first_predictions["prediction_period_end"])
    ).all()
    assert (
        pd.to_datetime(first_fits["max_train_target_end_date"])
        < pd.to_datetime(first_fits["prediction_start"])
    ).all()


def test_repeated_expanding_rf_window_run_is_deterministic_and_train_only(tmp_path) -> None:
    frame = _synthetic_frame()
    runner = Phase3DWindowSensitivityRunner(tmp_path, XNYSTradingCalendar())
    first_predictions, first_fits, first_preprocessing, first_metrics = runner.run_policy(
        frame, "expanding",
    )
    second_predictions, second_fits, second_preprocessing, second_metrics = runner.run_policy(
        frame, "expanding",
    )
    np.testing.assert_allclose(
        first_predictions["predicted_return"], second_predictions["predicted_return"],
        rtol=0.0, atol=1e-15,
    )
    assert (
        first_metrics["overall"]["ranking"]["rank_ic"]["mean"]
        == pytest.approx(
            second_metrics["overall"]["ranking"]["rank_ic"]["mean"], abs=1e-12,
        )
    )
    assert first_fits[["fit_id", "prediction_start", "prediction_end"]].equals(
        second_fits[["fit_id", "prediction_start", "prediction_end"]]
    )
    assert first_preprocessing.shape == second_preprocessing.shape
    assert first_preprocessing["fit_partition"].eq("train").all()
    assert first_preprocessing.groupby("fit_id").size().eq(52).all()
    assert first_predictions["test_used"].eq(False).all()
    assert first_fits["test_used"].eq(False).all()
    assert (
        pd.to_datetime(first_fits["max_train_target_end_date"])
        < pd.to_datetime(first_fits["prediction_start"])
    ).all()
