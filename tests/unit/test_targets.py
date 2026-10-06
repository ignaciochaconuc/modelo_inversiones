from datetime import date, datetime, timedelta, timezone
import pandas as pd
import pytest

from investment_system.features.targets import add_cross_sectional_rank, build_price_targets, build_training_dataset

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)

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
    def session_open(self, value: date): return NOW
    def session_close(self, value: date): return NOW

def market_frames(split_factor: float, start_price: float, post_price: float):
    days = list(pd.bdate_range("2025-01-02", periods=21).date)
    closes = [start_price] * 5 + [post_price] * 5 + [post_price * 1.1] + [post_price * 1.1] * 10
    raw = pd.DataFrame({
        "ticker": "TEST", "trading_date": days, "provider": "tiingo", "schema_version": "1",
        "ingested_at": NOW, "open": closes, "high": closes, "low": closes, "close": closes, "volume": 100.0,
    })
    actions = pd.DataFrame([{
        "ticker": "TEST", "effective_date": days[5], "action_type": "split", "provider": "tiingo",
        "split_factor": split_factor, "available_at": NOW, "ingested_at": NOW,
    }])
    return raw, actions

def test_target_handles_forward_two_for_one_split() -> None:
    targets = build_price_targets(*market_frames(2.0, 200.0, 100.0), WeekdayCalendar())
    assert targets.loc[0, "target_return_10d"] == pytest.approx(0.10)
    assert pd.isna(targets.loc[len(targets) - 1, "target_return_5d"])

def test_target_handles_forward_reverse_split() -> None:
    targets = build_price_targets(*market_frames(0.5, 50.0, 100.0), WeekdayCalendar())
    assert targets.loc[0, "target_return_10d"] == pytest.approx(0.10)

def test_target_uses_exact_calendar_session_and_does_not_skip_gap() -> None:
    raw, actions = market_frames(2.0, 200.0, 100.0)
    calendar = WeekdayCalendar()
    targets = build_price_targets(raw, actions, calendar)
    tenth_session = calendar.next_session(raw.loc[0, "trading_date"])
    for _ in range(9):
        tenth_session = calendar.next_session(tenth_session)
    assert tenth_session == raw.loc[10, "trading_date"]
    assert targets.loc[0, "target_return_10d"] == pytest.approx(0.10)
    missing = raw[raw["trading_date"] != tenth_session]
    missing_targets = build_price_targets(missing, actions, calendar)
    assert pd.isna(missing_targets.loc[missing_targets["decision_date"] == raw.loc[0, "trading_date"], "target_return_10d"].iloc[0])

def test_cross_sectional_rank_is_zero_to_one_with_average_ties() -> None:
    frame = pd.DataFrame({
        "ticker": ["A", "B", "C", "D"], "decision_date": date(2025, 1, 1),
        "target_return_10d": [0.0, 0.1, 0.1, 0.2],
    })
    ranked = add_cross_sectional_rank(frame, minimum_assets=4)
    assert ranked.loc[0, "target_rank_10d"] == 0
    assert ranked.loc[3, "target_rank_10d"] == 1
    assert ranked.loc[1, "target_rank_10d"] == ranked.loc[2, "target_rank_10d"] == pytest.approx(0.5)
    assert add_cross_sectional_rank(frame, minimum_assets=5)["target_rank_10d"].isna().all()

def test_target_contamination_looks_forward_and_rank_excludes_it() -> None:
    raw, actions = market_frames(1.0, 100.0, 100.0)
    event_day = raw.loc[10, "trading_date"]
    events = pd.DataFrame([{"event_date": event_day, "training_exclusion": True}])
    targets = build_price_targets(raw, actions, WeekdayCalendar(), events)
    origin = raw.loc[0, "trading_date"]
    row = targets[targets["decision_date"] == origin].iloc[0]
    assert row["target_corporate_action_contaminated_10d"]
    assert not row["target_10d_training_eligible"]

    cross = pd.DataFrame({
        "ticker": ["A", "B", "C"], "decision_date": origin,
        "target_return_10d": [0.1, 0.2, 0.3],
        "target_10d_training_eligible": [True, False, True],
    })
    assert add_cross_sectional_rank(cross, minimum_assets=3)["target_rank_10d"].isna().all()
    ranked = add_cross_sectional_rank(cross, minimum_assets=2)
    assert pd.isna(ranked.loc[1, "target_rank_10d"])

def test_training_eligibility_is_created_only_by_explicit_join() -> None:
    features = pd.DataFrame({
        "ticker": ["A"], "decision_date": [date(2025, 1, 1)], "model_eligible": [True],
        "feature_corporate_action_contaminated": [False],
    })
    targets = pd.DataFrame({
        "ticker": ["A"], "decision_date": [date(2025, 1, 1)],
        "target_10d_training_eligible": [True],
    })
    assert "training_eligible" not in features
    assert build_training_dataset(features, targets)["training_eligible"].iloc[0]
