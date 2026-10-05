from datetime import date, datetime, timezone
import pandas as pd
import pytest
from pydantic import ValidationError

from investment_system.core.exceptions import DataQualityError, PointInTimeViolation
from investment_system.core.time_utils import validate_available_at
from investment_system.data.normalization import build_split_adjusted_series, build_split_adjusted_series_as_of, extract_corporate_actions
from investment_system.data.schemas.market import CorporateAction, CorporateActionType, MarketBar
from investment_system.data.validation.market import validate_market_bars

NOW = datetime(2025, 1, 3, tzinfo=timezone.utc)

def bar(day: date, close: float, *, split: float = 1, dividend: float = 0) -> MarketBar:
    return MarketBar(ticker="AAPL", trading_date=day, provider="tiingo", open=close, high=close, low=close, close=close, volume=100, split_factor=split, dividend_cash=dividend, observed_at=NOW, available_at=NOW, ingested_at=NOW)

def frames(bars: list[MarketBar]):
    actions = extract_corporate_actions(bars)
    return pd.DataFrame([item.model_dump(mode="python") for item in bars]), pd.DataFrame([item.model_dump(mode="python") for item in actions]), actions

def test_two_for_one_split_removes_false_return() -> None:
    raw, actions, _ = frames([bar(date(2025, 1, 2), 200), bar(date(2025, 1, 3), 100, split=2)])
    adjusted = build_split_adjusted_series(raw, actions)
    assert adjusted["split_adjusted_close"].tolist() == [100, 100]
    assert adjusted["split_adjusted_volume"].tolist() == [200, 100]

def test_reverse_split_uses_new_shares_per_old_share() -> None:
    raw, actions, _ = frames([bar(date(2025, 1, 2), 50), bar(date(2025, 1, 3), 100, split=0.5)])
    adjusted = build_split_adjusted_series(raw, actions)
    assert adjusted["split_adjusted_close"].tolist() == [100, 100]
    assert adjusted["split_adjusted_volume"].tolist() == [50, 100]

def test_dividend_is_stored_but_does_not_adjust_price() -> None:
    raw, actions_frame, actions = frames([bar(date(2025, 1, 2), 100), bar(date(2025, 1, 3), 99, dividend=1)])
    adjusted = build_split_adjusted_series(raw, actions_frame)
    assert len(actions) == 1 and actions[0].dividend_cash == 1
    assert adjusted["split_adjusted_close"].tolist() == [100, 99]

def test_ohlc_quality_and_duplicates() -> None:
    with pytest.raises(ValidationError, match="high"):
        MarketBar(ticker="AAPL", trading_date=date(2025, 1, 2), provider="tiingo", open=10, high=9, low=8, close=10, volume=1, ingested_at=NOW)
    duplicate = bar(date(2025, 1, 2), 10)
    with pytest.raises(DataQualityError, match="duplicate"):
        validate_market_bars([duplicate, duplicate])

def test_bar_cannot_be_used_before_available_at() -> None:
    market_bar = bar(date(2025, 1, 2), 10)
    with pytest.raises(PointInTimeViolation):
        validate_available_at(market_bar.available_at, datetime(2025, 1, 2, tzinfo=timezone.utc))

def split_action(*, available_at: datetime) -> CorporateAction:
    return CorporateAction(
        ticker="AAPL", effective_date=date(2025, 6, 1), action_type=CorporateActionType.SPLIT,
        split_factor=2, provider="tiingo", observed_at=available_at,
        available_at=available_at, ingested_at=available_at,
    )

def historical_raw() -> pd.DataFrame:
    bars = [bar(date(2025, 1, 1), 100), bar(date(2025, 1, 2), 110)]
    return pd.DataFrame([item.model_dump(mode="python") for item in bars])

def test_future_split_does_not_affect_earlier_decision() -> None:
    action = split_action(available_at=datetime(2025, 6, 1, 20, tzinfo=timezone.utc))
    result = build_split_adjusted_series_as_of(
        historical_raw(), pd.DataFrame([action.model_dump(mode="python")]),
        decision_date=date(2025, 1, 3), decision_time=datetime(2025, 1, 3, 21, tzinfo=timezone.utc),
    )
    assert result["split_adjusted_close"].tolist() == [100, 110]

def test_known_split_adjusts_history_after_effective_date() -> None:
    action = split_action(available_at=datetime(2025, 6, 1, 20, tzinfo=timezone.utc))
    result = build_split_adjusted_series_as_of(
        historical_raw(), pd.DataFrame([action.model_dump(mode="python")]),
        decision_date=date(2025, 6, 2), decision_time=datetime(2025, 6, 2, 21, tzinfo=timezone.utc),
    )
    assert result["split_adjusted_close"].tolist() == [50, 55]
    assert set(result["normalization_basis"]) == {"as_of"}

def test_effective_but_unavailable_split_is_excluded() -> None:
    action = split_action(available_at=datetime(2025, 6, 3, 20, tzinfo=timezone.utc))
    result = build_split_adjusted_series_as_of(
        historical_raw(), pd.DataFrame([action.model_dump(mode="python")]),
        decision_date=date(2025, 6, 2), decision_time=datetime(2025, 6, 2, 21, tzinfo=timezone.utc),
    )
    assert result["split_adjusted_close"].tolist() == [100, 110]
