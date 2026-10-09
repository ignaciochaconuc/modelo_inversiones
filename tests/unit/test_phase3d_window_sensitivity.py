from datetime import date

import pandas as pd
import pytest

from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.models.walkforward import (
    Phase3DWalkForwardRunner,
    build_walkforward_schedule,
    validate_schedule,
    xnys_sessions,
)
from investment_system.models.window_sensitivity import (
    MATERIAL_IMPROVEMENT_THRESHOLD,
    WINDOW_IC_TOLERANCE,
    nominal_window_start,
    select_training_window,
    window_deltas,
    window_training_masks,
)


@pytest.mark.parametrize(("prediction_start", "policy", "expected"), [
    (date(2016, 1, 4), "expanding", date(2010, 1, 4)),
    (date(2016, 1, 4), "trailing-8y", date(2010, 1, 4)),
    (date(2016, 1, 4), "trailing-5y", date(2011, 1, 4)),
    (date(2021, 1, 4), "trailing-8y", date(2013, 1, 4)),
    (date(2021, 1, 4), "trailing-5y", date(2016, 1, 4)),
    (date(2020, 2, 29), "trailing-8y", date(2012, 2, 29)),
    (date(2020, 2, 29), "trailing-5y", date(2015, 2, 28)),
])
def test_nominal_window_boundaries_use_calendar_years_and_history_floor(
    prediction_start, policy, expected,
) -> None:
    assert nominal_window_start(prediction_start, policy) == expected


@pytest.mark.parametrize("policy", ["expanding", "trailing-8y", "trailing-5y"])
def test_window_purge_is_strict_and_removes_equality(policy) -> None:
    frame = pd.DataFrame({
        "decision_date": [
            date(2010, 1, 4), date(2011, 1, 4), date(2015, 12, 1),
            date(2015, 12, 2), date(2016, 1, 4),
        ],
        "target_end_date_20d": [
            date(2010, 2, 2), date(2011, 2, 2), date(2015, 12, 31),
            date(2016, 1, 4), date(2016, 2, 2),
        ],
    })
    nominal, purged, window_start, nominal_end = window_training_masks(
        frame, date(2016, 1, 4), policy,
    )
    assert nominal_end == date(2015, 12, 2)
    assert frame.loc[nominal, "decision_date"].min() >= window_start
    assert frame.loc[purged, "target_end_date_20d"].max() < date(2016, 1, 4)
    assert (frame.loc[purged, "decision_date"] < date(2016, 1, 4)).all()
    assert date(2016, 1, 4) not in frame.loc[purged, "target_end_date_20d"].tolist()


def test_annual_schedule_has_six_contiguous_xnys_periods() -> None:
    calendar = XNYSTradingCalendar()
    sessions = xnys_sessions(calendar, date(2016, 1, 1), date(2021, 12, 31))
    periods = build_walkforward_schedule(
        calendar, "annual", start=date(2016, 1, 1), end=date(2021, 12, 31),
    )
    assert len(periods) == 6
    assert [period.prediction_start.year for period in periods] == list(range(2016, 2022))
    validate_schedule(periods, sessions)


def _metrics(
    mean: float, *, worst: float = 0.01, icir: float = 0.2,
    pct: float = 0.55, top10: float = 0.01,
) -> dict:
    return {
        "overall": {"ranking": {
            "rank_ic": {"mean": mean, "icir": icir, "pct_positive": pct},
            "top10": {"average_top10_uplift": top10},
        }},
        "stability": {"worst_year_ic": worst, "year_ic_std": 0.02},
    }


def test_selection_prefers_expanding_inside_tolerance() -> None:
    assert WINDOW_IC_TOLERANCE == 0.003
    metrics = {
        "expanding": _metrics(0.0600),
        "trailing-8y": _metrics(0.0629),
        "trailing-5y": _metrics(0.0610),
    }
    selection = select_training_window(metrics)
    assert selection.raw_best_window == "trailing-8y"
    assert selection.selected_window == "expanding"
    assert selection.equivalent_windows == ("expanding", "trailing-8y", "trailing-5y")


def test_selection_uses_secondary_tie_breaks_and_selects_trailing_outside_tolerance() -> None:
    metrics = {
        "expanding": _metrics(0.0500),
        "trailing-8y": _metrics(0.0540, worst=0.01),
        "trailing-5y": _metrics(0.0540, worst=0.02),
    }
    selection = select_training_window(metrics)
    assert selection.raw_best_window == "trailing-5y"
    assert selection.selected_window == "trailing-5y"


def test_material_improvement_flag_uses_predeclared_threshold() -> None:
    assert MATERIAL_IMPROVEMENT_THRESHOLD == 0.005
    metrics = {
        "expanding": _metrics(0.0500),
        "trailing-8y": _metrics(0.0550),
        "trailing-5y": _metrics(0.054999),
    }
    deltas = window_deltas(metrics)
    assert deltas["trailing-8y"]["material_improvement_vs_expanding"] is True
    assert deltas["trailing-5y"]["material_improvement_vs_expanding"] is False


def test_frozen_rf_small_is_exact() -> None:
    factory, preprocessor, version, parameters = Phase3DWalkForwardRunner._model_factory("rf-small")
    model = factory()
    expected = {
        "n_estimators": 300, "max_depth": 4, "min_samples_leaf": 100,
        "max_features": "sqrt", "bootstrap": True, "random_state": 42, "n_jobs": -1,
    }
    assert parameters == expected
    assert {key: model.get_params()[key] for key in expected} == expected
    assert preprocessor.__name__ == "TreePreprocessor"
    assert version == "tree-preprocessing-v1"
