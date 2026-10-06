from datetime import date, datetime, time, timedelta, timezone

import pandas as pd

from investment_system.data.corporate_actions import (
    add_feature_contamination_flags, detect_corporate_action_events,
)
from investment_system.data.full_universe import FullUniverseBuild


class WeekdayCalendar:
    def is_session(self, value: date) -> bool: return value.weekday() < 5
    def next_session(self, value: date) -> date:
        value += timedelta(days=1)
        while not self.is_session(value): value += timedelta(days=1)
        return value
    def previous_session(self, value: date) -> date:
        value -= timedelta(days=1)
        while not self.is_session(value): value -= timedelta(days=1)
        return value
    def session_open(self, value: date): return datetime.combine(value, time(14, 30), timezone.utc)
    def session_close(self, value: date): return datetime.combine(value, time(21), timezone.utc)


def fixture_frames(*, explained: bool) -> tuple[pd.DataFrame, pd.DataFrame]:
    days = list(pd.bdate_range("2025-01-02", periods=5).date)
    closes = [100.0, 100.0, 50.0, 51.0, 52.0]
    adjusted = [50.0, 50.0, 50.0, 51.0, 52.0] if explained else closes
    known = datetime(2025, 1, 6, 20, tzinfo=timezone.utc)
    raw = pd.DataFrame({
        "ticker": "TEST", "trading_date": days, "provider": "tiingo", "schema_version": "1",
        "open": closes, "high": closes, "low": closes, "close": closes, "volume": 100,
        "adjusted_close": adjusted, "split_factor": 1.0, "dividend_cash": [0, 0, 50 if explained else 0, 0, 0],
        "available_at": [datetime.combine(day, time(20), timezone.utc) for day in days],
        "ingested_at": known,
    })
    actions = pd.DataFrame([{
        "ticker": "TEST", "effective_date": days[2], "action_type": "dividend", "provider": "tiingo",
        "dividend_cash": 50.0, "split_factor": None, "available_at": known, "ingested_at": known,
    }]) if explained else pd.DataFrame()
    return raw, actions


def test_unexplained_discontinuity_is_detected_but_not_given_invented_exclusion() -> None:
    raw, actions = fixture_frames(explained=False)
    before = raw.copy(deep=True)
    events = detect_corporate_action_events(raw, actions, ticker="TEST")
    assert events.iloc[0]["event_type"] == "unexplained_price_discontinuity"
    assert not events.iloc[0]["training_exclusion"]
    pd.testing.assert_frame_equal(raw, before)


def test_known_complex_evidence_and_manual_override_are_auditable() -> None:
    raw, actions = fixture_frames(explained=True)
    events = detect_corporate_action_events(raw, actions, ticker="TEST", overrides=[{
        "ticker": "TEST", "date": "2025-01-06", "classification": "complex_recapitalization",
        "training_exclusion": True, "known_at": "2025-01-06T19:00:00Z", "notes": "reviewed",
    }])
    assert set(events["source"]) == {"heuristic", "manual_override"}
    assert events["training_exclusion"].all()


def test_feature_contamination_is_point_in_time_safe() -> None:
    raw, actions = fixture_frames(explained=True)
    events = detect_corporate_action_events(raw, actions, ticker="TEST")
    event_day = events.iloc[0]["event_date"]
    features = pd.DataFrame({
        "ticker": ["TEST"] * 3,
        "decision_date": [WeekdayCalendar().previous_session(event_day), event_day, WeekdayCalendar().next_session(event_day)],
        "decision_time": [
            datetime(2025, 1, 3, 20, 15, tzinfo=timezone.utc),
            datetime(2025, 1, 6, 19, 59, tzinfo=timezone.utc),
            datetime(2025, 1, 7, 20, 15, tzinfo=timezone.utc),
        ],
    })
    flagged = add_feature_contamination_flags(features, events, WeekdayCalendar())
    assert flagged["feature_corporate_action_contaminated"].tolist() == [False, False, True]


def test_volatility_percentile_warmup_is_expected_not_anomaly() -> None:
    frame = pd.DataFrame({
        "model_eligible": [True, True], "history_count": [253, 280],
        "percentile_volatility_252d": [float("nan"), 0.5],
    })
    for column in __import__("investment_system.data.schemas.features", fromlist=["QUANTITATIVE_FEATURE_COLUMNS"]).QUANTITATIVE_FEATURE_COLUMNS:
        if column not in frame:
            frame[column] = 1.0
    expected, unexpected = FullUniverseBuild._nan_diagnostics(frame)
    assert expected["percentile_volatility_252d"]["count"] == 1
    assert "percentile_volatility_252d" not in unexpected
