from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from investment_system.data.normalization import extract_corporate_actions
from investment_system.data.schemas.features import QUANTITATIVE_FEATURE_COLUMNS
from investment_system.data.schemas.market import MarketBar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.storage.duckdb_store import DuckDBStore
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.universe import UniverseConfig
from investment_system.features.store_builder import QuantitativeFeatureStoreBuilder

class WeekdayCalendar:
    def is_session(self, value: date) -> bool: return value.weekday() < 5
    def previous_session(self, value: date) -> date: return value - timedelta(days=1)
    def next_session(self, value: date) -> date: return value + timedelta(days=1)
    def session_open(self, value: date): return datetime.combine(value, time(14, 30), timezone.utc)
    def session_close(self, value: date): return datetime.combine(value, time(21), timezone.utc)

def universe() -> UniverseConfig:
    return UniverseConfig.model_validate({
        "benchmark": "SPY", "asset_class": "US_EQUITY", "universe_type": "development_fixed",
        "description": "test", "universe": {"name": "test", "point_in_time": False, "survivorship_bias_warning": True, "as_of": "2025-01-01"},
        "tickers": ["AAPL"],
    })

def make_bars(ticker: str, days: list[date], *, split_day: date | None = None) -> list[MarketBar]:
    bars = []
    for index, day in enumerate(days):
        base = 100 + index + index * index / 1000
        split = 2.0 if day == split_day else 1.0
        price = base / 2 if split_day and day >= split_day else base
        available = datetime.combine(day, time(20), ZoneInfo("America/New_York"))
        bars.append(MarketBar(
            ticker=ticker, trading_date=day, provider="tiingo", open=price, high=price * 1.01,
            low=price * 0.99, close=price, volume=1000 + index, split_factor=split,
            observed_at=available - timedelta(hours=4), available_at=available, ingested_at=available,
        ))
    return bars

def persist_bars(store: MarketDataStore, bars: list[MarketBar]) -> None:
    store.upsert_bars(bars)
    actions = extract_corporate_actions(bars)
    store.replace_actions_for_dates(bars[0].ticker, {bar.trading_date for bar in bars}, actions)

def builder(tmp_path, days: list[date]) -> tuple[QuantitativeFeatureStoreBuilder, MarketDataStore]:
    market = MarketDataStore(tmp_path / "raw", tmp_path / "processed")
    feature_store = QuantitativeFeatureStore(tmp_path / "features", tmp_path / "targets")
    return QuantitativeFeatureStoreBuilder(
        market, feature_store, WeekdayCalendar(), universe(), raw_history_start=days[0],
        feature_history_start=days[0], minimum_rank_assets=2,
    ), market

def test_future_data_and_split_do_not_change_historical_features(tmp_path) -> None:
    days = list(pd.bdate_range("2024-01-02", periods=90).date)
    service, market = builder(tmp_path, days)
    persist_bars(market, make_bars("AAPL", days[:70]))
    persist_bars(market, make_bars("SPY", days[:70]))
    decision = days[60]
    before = service.build_ticker("AAPL", decision, decision, market.read_bars("SPY"), market.read_actions("SPY"))

    future_days = days[70:]
    persist_bars(market, make_bars("AAPL", future_days, split_day=future_days[5]))
    persist_bars(market, make_bars("SPY", future_days))
    after = service.build_ticker("AAPL", decision, decision, market.read_bars("SPY"), market.read_actions("SPY"))
    pd.testing.assert_frame_equal(before, after, check_dtype=False)

def test_warmup_ipo_history_and_model_eligibility(tmp_path) -> None:
    days = list(pd.bdate_range("2023-01-02", periods=280).date)
    service, market = builder(tmp_path, days)
    persist_bars(market, make_bars("AAPL", days))
    persist_bars(market, make_bars("SPY", days))
    build_result = service.build(["AAPL"], days[0], days[-1], persist=True)
    result = build_result.features
    assert result["decision_date"].min() == days[0]
    assert not result.iloc[0]["has_20d_history"]
    assert pd.isna(result.iloc[0]["return_1d"])
    assert result.iloc[251]["has_252d_history"]
    assert not result.iloc[251]["model_eligible"]
    assert result.iloc[252]["model_eligible"]
    assert result["sector"].isna().all() and result["industry"].isna().all()
    assert build_result.manifest["normalization_version"] == "split-adjusted-as-of-v1"
    assert build_result.manifest["universe_point_in_time"] is False
    assert (tmp_path / "features" / "quantitative" / "manifest.json").exists()

def test_feature_and_target_storage_are_separate_and_idempotent(tmp_path) -> None:
    store = QuantitativeFeatureStore(tmp_path / "features", tmp_path / "targets")
    features = pd.DataFrame({
        "ticker": ["AAPL"], "decision_date": [date(2025, 1, 2)],
        "decision_time": [datetime(2025, 1, 3, tzinfo=timezone.utc)], "return_1d": [0.1],
    })
    targets = pd.DataFrame({"ticker": ["AAPL"], "decision_date": [date(2025, 1, 2)], "target_return_10d": [0.2]})
    store.write_features(features); store.write_features(features)
    store.write_targets(targets); store.write_targets(targets)
    manifest_path = store.write_manifest({"feature_schema_version": "2", "benchmark": "SPY"})
    assert len(store.read_features()) == 1
    assert len(store.read_targets()) == 1
    assert not set(store.read_features()).intersection({"target_return_10d"})
    assert not set(store.read_targets()).intersection(QUANTITATIVE_FEATURE_COLUMNS)
    assert manifest_path.exists()
    with DuckDBStore() as database:
        queried = database.query_parquet(tmp_path / "features" / "quantitative" / "year=*" / "data.parquet")
    assert len(queried) == 1 and queried.iloc[0]["ticker"] == "AAPL"
