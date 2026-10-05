from datetime import date, datetime, timezone
import pandas as pd
import pytest
from pydantic import ValidationError

from investment_system.core.exceptions import DataQualityError, PointInTimeViolation
from investment_system.core.time_utils import validate_available_at
from investment_system.data.normalization import build_split_adjusted_series, extract_corporate_actions
from investment_system.data.schemas.market import MarketBar
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
