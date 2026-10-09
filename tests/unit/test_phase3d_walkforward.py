from datetime import date

import pandas as pd
import pytest

from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.models.walkforward import (
    FREQUENCIES,
    RETRAIN_IC_TOLERANCE,
    Phase3DWalkForwardRunner,
    build_walkforward_schedule,
    dynamic_training_masks,
    model_age_bucket,
    select_operational_frequency,
    validate_schedule,
    xnys_sessions,
)


@pytest.mark.parametrize("frequency,expected", [
    ("monthly", 12), ("quarterly", 4), ("semiannual", 2), ("annual", 1),
])
def test_xnys_walkforward_schedules_are_contiguous_without_overlap(frequency, expected) -> None:
    calendar = XNYSTradingCalendar()
    sessions = xnys_sessions(calendar, date(2019, 1, 1), date(2019, 12, 31))
    periods = build_walkforward_schedule(
        calendar, frequency, start=date(2019, 1, 1), end=date(2019, 12, 31)
    )
    assert len(periods) == expected
    validate_schedule(periods, sessions)
    assert periods[0].prediction_start == date(2019, 1, 2)
    assert periods[-1].prediction_end == date(2019, 12, 31)


def test_dynamic_purge_removes_equality_and_expanding_window_never_uses_future() -> None:
    frame = pd.DataFrame({
        "decision_date": [date(2010, 1, 4), date(2015, 12, 1), date(2015, 12, 2), date(2016, 1, 4)],
        "target_end_date_20d": [date(2010, 2, 2), date(2015, 12, 31), date(2016, 1, 4), date(2016, 2, 2)],
    })
    nominal, purged, nominal_end = dynamic_training_masks(frame, date(2016, 1, 4))
    assert nominal_end == date(2015, 12, 2)
    assert nominal.sum() == 3
    assert purged.sum() == 2
    assert frame.loc[purged, "target_end_date_20d"].max() < date(2016, 1, 4)
    assert date(2016, 1, 4) not in frame.loc[purged, "target_end_date_20d"].tolist()

    previous_rows = 0
    previous_end = date(2010, 1, 4)
    for prediction_start in (date(2016, 1, 4), date(2016, 2, 1), date(2016, 3, 1)):
        _, current, _ = dynamic_training_masks(frame, prediction_start)
        assert current.sum() >= previous_rows
        assert frame.loc[current, "decision_date"].min() == date(2010, 1, 4)
        assert frame.loc[current, "decision_date"].max() >= previous_end
        assert (frame.loc[current, "decision_date"] < prediction_start).all()
        previous_rows = int(current.sum())
        previous_end = frame.loc[current, "decision_date"].max()


def _policy(ic: float, retrains: int, worst: float = 0.0, icir: float = .1) -> dict:
    return {
        "overall": {"ranking": {
            "rank_ic": {"mean": ic, "icir": icir, "pct_positive": .55},
            "top10": {"average_top10_uplift": .01},
        }},
        "stability": {"worst_year_ic": worst},
        "operational_cost": {"number_of_retrains": retrains},
    }


def test_frequency_selection_prefers_cheapest_policy_inside_tolerance() -> None:
    assert RETRAIN_IC_TOLERANCE == .003
    policies = {
        "monthly": _policy(.0500, 72),
        "quarterly": _policy(.0495, 24),
        "semiannual": _policy(.0480, 12),
        "annual": _policy(.0469, 6),
    }
    selection = select_operational_frequency("rf-small", policies)
    assert selection.raw_best_frequency == "monthly"
    assert selection.selected_frequency == "semiannual"
    assert selection.delta_vs_best_ic == pytest.approx(-.002)
    assert selection.retrain_count == 12
    assert select_operational_frequency("rf-small", policies) == selection


def test_frozen_configs_and_model_age_boundaries() -> None:
    rf_factory, rf_preprocessor, rf_version, rf_parameters = Phase3DWalkForwardRunner._model_factory("rf-small")
    rf = rf_factory()
    assert rf.get_params()["n_estimators"] == 300
    assert rf.get_params()["max_depth"] == 4
    assert rf.get_params()["min_samples_leaf"] == 100
    assert rf.get_params()["max_features"] == "sqrt"
    assert rf.get_params()["bootstrap"] is True
    assert rf.get_params()["random_state"] == 42
    assert rf.get_params()["n_jobs"] == -1
    ridge_factory, _, _, ridge_parameters = Phase3DWalkForwardRunner._model_factory("ridge-100")
    assert ridge_factory().get_params()["alpha"] == 100.0
    assert rf_parameters == {key: rf.get_params()[key] for key in rf_parameters}
    assert ridge_parameters == {"alpha": 100.0}
    assert [model_age_bucket(value) for value in (0, 20, 21, 40, 41, 60, 61, 120, 121)] == [
        "0-20", "0-20", "21-40", "21-40", "41-60", "41-60",
        "61-120", "61-120", "121+",
    ]
    with pytest.raises(ValueError, match="negative"):
        model_age_bucket(-1)

