from datetime import date, datetime, timedelta, timezone

import pandas as pd
import pytest
from pydantic import ValidationError

from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.features.targets import (
    SUPPORTED_HORIZONS,
    add_cross_sectional_rank,
    build_price_targets,
)
from investment_system.models.contracts import TargetSpec


class WeekdayCalendar:
    def is_session(self, value: date) -> bool:
        return value.weekday() < 5

    def next_session(self, value: date) -> date:
        value += timedelta(days=1)
        while not self.is_session(value):
            value += timedelta(days=1)
        return value

    def previous_session(self, value: date) -> date:
        value -= timedelta(days=1)
        while not self.is_session(value):
            value -= timedelta(days=1)
        return value


def _bars(periods: int = 25) -> pd.DataFrame:
    days = list(pd.bdate_range("2024-12-02", periods=periods).date)
    prices = [100.0 + index for index in range(periods)]
    return pd.DataFrame({
        "ticker": "TEST",
        "trading_date": days,
        "provider": "test",
        "schema_version": "1",
        "ingested_at": datetime(2025, 2, 1, tzinfo=timezone.utc),
        "open": prices,
        "high": prices,
        "low": prices,
        "close": prices,
        "volume": 100.0,
    })


def test_symmetric_positive_targets_and_na() -> None:
    targets = build_price_targets(_bars(), pd.DataFrame(), WeekdayCalendar())
    for horizon in SUPPORTED_HORIZONS:
        returns = targets[f"target_return_{horizon}d"]
        positives = targets[f"target_positive_{horizon}d"]
        assert (positives[returns.notna()] == (returns[returns.notna()] > 0).astype(int)).all()
        assert positives[returns.isna()].isna().all()


def test_all_rank_horizons_use_eligible_values_and_average_ties() -> None:
    frame = pd.DataFrame({"ticker": list("ABCD"), "decision_date": date(2025, 1, 2)})
    for horizon in SUPPORTED_HORIZONS:
        frame[f"target_return_{horizon}d"] = [0.0, 0.1, 0.1, 0.2]
        frame[f"target_{horizon}d_training_eligible"] = [True, True, True, True]
    ranked = add_cross_sectional_rank(frame, minimum_assets=4)
    for horizon in SUPPORTED_HORIZONS:
        values = ranked[f"target_rank_{horizon}d"]
        assert values.tolist() == pytest.approx([0.0, 0.5, 0.5, 1.0])

    frame["target_5d_training_eligible"] = [True, True, True, False]
    ranked = add_cross_sectional_rank(frame, minimum_assets=4)
    assert ranked["target_rank_5d"].isna().all()
    ranked = add_cross_sectional_rank(frame, minimum_assets=3)
    assert pd.isna(ranked.loc[3, "target_rank_5d"])


def test_target_end_date_is_exact_xnys_future_session() -> None:
    calendar = XNYSTradingCalendar()
    origin = date(2024, 12, 20)
    sessions = [origin]
    for _ in range(20):
        sessions.append(calendar.next_session(sessions[-1]))
    prices = [100.0 + index for index in range(len(sessions))]
    bars = pd.DataFrame({
        "ticker": "TEST", "trading_date": sessions, "provider": "test",
        "schema_version": "1", "ingested_at": datetime(2025, 2, 1, tzinfo=timezone.utc),
        "open": prices, "high": prices, "low": prices, "close": prices, "volume": 100.0,
    })
    targets = build_price_targets(bars, pd.DataFrame(), calendar)
    row = targets.loc[targets["decision_date"] == origin].iloc[0]
    assert row["target_end_date_5d"] == date(2024, 12, 30)
    assert row["target_end_date_10d"] == sessions[10]
    assert row["target_end_date_20d"] == sessions[20]


@pytest.mark.parametrize("task,prefix", [
    ("regression", "target_return"),
    ("classification", "target_positive"),
    ("ranking", "target_rank"),
])
@pytest.mark.parametrize("horizon", SUPPORTED_HORIZONS)
def test_target_spec_resolves_every_task_horizon(task: str, prefix: str, horizon: int) -> None:
    spec = TargetSpec(task=task, horizon=horizon)
    assert spec.target_column == f"{prefix}_{horizon}d"
    assert spec.eligibility_column == f"target_{horizon}d_training_eligible"
    assert spec.target_end_date_column == f"target_end_date_{horizon}d"
    assert spec.purge_horizon == horizon


def test_target_spec_rejects_invalid_values() -> None:
    with pytest.raises(ValidationError):
        TargetSpec(task="forecast", horizon=10)
    with pytest.raises(ValidationError):
        TargetSpec(task="regression", horizon=7)
