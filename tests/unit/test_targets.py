from datetime import date, datetime, timedelta, timezone
import pandas as pd
import pytest

from investment_system.features.targets import add_cross_sectional_rank, build_price_targets

NOW = datetime(2025, 1, 1, tzinfo=timezone.utc)

def market_frames(split_factor: float, start_price: float, post_price: float):
    days = [date(2025, 1, 1) + timedelta(days=index) for index in range(11)]
    closes = [start_price] * 5 + [post_price] * 5 + [post_price * 1.1]
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
    targets = build_price_targets(*market_frames(2.0, 200.0, 100.0))
    assert targets.loc[0, "target_return_10d"] == pytest.approx(0.10)
    assert pd.isna(targets.loc[len(targets) - 1, "target_return_5d"])

def test_target_handles_forward_reverse_split() -> None:
    targets = build_price_targets(*market_frames(0.5, 50.0, 100.0))
    assert targets.loc[0, "target_return_10d"] == pytest.approx(0.10)

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
