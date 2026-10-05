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
    assert build_result.manifest["feature_schema_version"] == "3"
    assert build_result.manifest["quantitative_feature_version"] == "quantitative-v1.1"
    assert build_result.manifest["universe_point_in_time"] is False
    assert set(build_result.report["feature_build_seconds_by_ticker"]) == {"AAPL"}
    assert (tmp_path / "features" / "quantitative" / "manifest.json").exists()

def test_history_count_and_eligibility_do_not_reset_after_split(tmp_path) -> None:
    days = list(pd.bdate_range("2022-01-03", periods=330).date)
    service, market = builder(tmp_path, days)
    split_day = days[310]
    persist_bars(market, make_bars("AAPL", days, split_day=split_day))
    persist_bars(market, make_bars("SPY", days))
    result = service.build_ticker("AAPL", days[305], days[315], market.read_bars("SPY"), market.read_actions("SPY"))
    before = result[result["decision_date"] == days[309]].iloc[0]
    on_split = result[result["decision_date"] == split_day].iloc[0]
    after = result[result["decision_date"] == days[311]].iloc[0]
    assert (before["history_count"], on_split["history_count"], after["history_count"]) == (310, 311, 312)
    assert before["model_eligible"] and on_split["model_eligible"] and after["model_eligible"]

def test_bar_after_cutoff_is_excluded_then_available_later(tmp_path) -> None:
    days = list(pd.bdate_range("2025-01-02", periods=80).date)
    service, market = builder(tmp_path, days)
    asset = make_bars("AAPL", days)
    delayed_day = days[60]
    delayed = asset[60].model_copy(update={
        "available_at": datetime.combine(delayed_day, time(21), ZoneInfo("America/New_York")),
        "ingested_at": datetime.combine(delayed_day, time(21), ZoneInfo("America/New_York")),
    })
    asset[60] = delayed
    persist_bars(market, asset)
    persist_bars(market, make_bars("SPY", days))
    result = service.build_ticker("AAPL", delayed_day, days[61], market.read_bars("SPY"), market.read_actions("SPY"))
    assert delayed_day not in set(result["decision_date"])
    next_row = result[result["decision_date"] == days[61]].iloc[0]
    assert next_row["history_count"] == 62

def test_historical_late_bar_does_not_rewrite_earlier_decision(tmp_path) -> None:
    days = list(pd.bdate_range("2025-01-02", periods=80).date)
    service, market = builder(tmp_path, days)
    asset = make_bars("AAPL", days)
    late_bar = asset.pop(40).model_copy(update={
        "available_at": datetime.combine(days[45], time(20), ZoneInfo("America/New_York")),
        "ingested_at": datetime.combine(days[45], time(20), ZoneInfo("America/New_York")),
    })
    persist_bars(market, asset)
    persist_bars(market, make_bars("SPY", days))
    decision = days[43]
    before = service.build_ticker("AAPL", decision, decision, market.read_bars("SPY"), market.read_actions("SPY"))
    persist_bars(market, [late_bar])
    after = service.build_ticker("AAPL", decision, decision, market.read_bars("SPY"), market.read_actions("SPY"))
    pd.testing.assert_frame_equal(before, after, check_dtype=False)
    later = service.build_ticker("AAPL", days[45], days[45], market.read_bars("SPY"), market.read_actions("SPY"))
    assert later.iloc[0]["history_count"] == 46

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

def test_authoritative_range_rebuild_removes_stale_rows(tmp_path) -> None:
    store = QuantitativeFeatureStore(tmp_path / "features", tmp_path / "targets")
    original = pd.DataFrame({
        "ticker": ["AAPL", "AAPL", "MSFT"],
        "decision_date": [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 3)],
        "value": [1, 2, 3],
    })
    store.write_features(original)
    replacement = original.iloc[[0]].assign(value=10)
    store.replace_feature_range(replacement, ["AAPL"], date(2025, 1, 2), date(2025, 1, 3))
    result = store.read_features().sort_values(["ticker", "decision_date"]).reset_index(drop=True)
    assert len(result) == 2
    assert result[result["ticker"] == "AAPL"]["value"].tolist() == [10]
    assert result[result["ticker"] == "MSFT"]["value"].tolist() == [3]


def _naive_segments(service, days, asset_actions, benchmark_actions, asset_raw, benchmark_raw):
    segments = []
    signature = None
    for day in days:
        decision_time = service.decision_time(day)
        current = (
            service._split_signature(asset_actions, day, decision_time),
            service._split_signature(benchmark_actions, day, decision_time),
            service._late_bar_signature(asset_raw, day, decision_time),
            service._late_bar_signature(benchmark_raw, day, decision_time),
        )
        if current != signature:
            segments.append([])
            signature = current
        segments[-1].append(day)
    return segments


def test_optimized_history_counts_equal_naive_reference_with_delayed_bars(tmp_path) -> None:
    days = list(pd.bdate_range("2025-01-02", periods=80).date)
    service, market = builder(tmp_path, days)
    bars = make_bars("AAPL", days)
    for source_index, available_index in ((5, 8), (31, 45), (60, 61)):
        bars[source_index] = bars[source_index].model_copy(update={
            "available_at": datetime.combine(days[available_index], time(20), ZoneInfo("America/New_York")),
            "ingested_at": datetime.combine(days[available_index], time(20), ZoneInfo("America/New_York")),
        })
    persist_bars(market, bars)
    raw = market.read_bars("AAPL")
    assert service._history_counts(raw, days) == [service._history_count(raw, day) for day in days]


def test_event_segments_equal_naive_signatures_for_splits_and_delays(tmp_path) -> None:
    days = list(pd.bdate_range("2024-01-02", periods=100).date)
    service, market = builder(tmp_path, days)
    asset = make_bars("AAPL", days, split_day=days[70])
    asset[25] = asset[25].model_copy(update={
        "available_at": datetime.combine(days[40], time(20), ZoneInfo("America/New_York")),
        "ingested_at": datetime.combine(days[40], time(20), ZoneInfo("America/New_York")),
    })
    benchmark = make_bars("SPY", days, split_day=days[80])
    benchmark[10] = benchmark[10].model_copy(update={
        "available_at": datetime.combine(days[15], time(20), ZoneInfo("America/New_York")),
        "ingested_at": datetime.combine(days[15], time(20), ZoneInfo("America/New_York")),
    })
    persist_bars(market, asset); persist_bars(market, benchmark)
    inputs = (market.read_actions("AAPL"), market.read_actions("SPY"),
              market.read_bars("AAPL"), market.read_bars("SPY"))
    assert service._segments(days, *inputs) == _naive_segments(service, days, *inputs)


def test_optimized_builder_is_numerically_equivalent_to_naive_reference(tmp_path) -> None:
    days = list(pd.bdate_range("2023-01-02", periods=330).date)
    service, market = builder(tmp_path, days)
    asset = make_bars("AAPL", days, split_day=days[290])
    asset[100] = asset[100].model_copy(update={
        "available_at": datetime.combine(days[110], time(20), ZoneInfo("America/New_York")),
        "ingested_at": datetime.combine(days[110], time(20), ZoneInfo("America/New_York")),
    })
    persist_bars(market, asset); persist_bars(market, make_bars("SPY", days))
    benchmark_raw, benchmark_actions = market.read_bars("SPY"), market.read_actions("SPY")
    optimized = service.build_ticker("AAPL", days[0], days[-1], benchmark_raw, benchmark_actions)

    original_segments, original_counts = service._segments, service._history_counts
    service._segments = lambda candidate_days, *inputs: _naive_segments(service, candidate_days, *inputs)
    service._history_counts = lambda raw, candidate_days: [service._history_count(raw, day) for day in candidate_days]
    try:
        reference = service.build_ticker("AAPL", days[0], days[-1], benchmark_raw, benchmark_actions)
    finally:
        service._segments, service._history_counts = original_segments, original_counts
    pd.testing.assert_frame_equal(optimized, reference, check_exact=False, rtol=1e-12, atol=1e-12)


def test_build_excludes_raw_bar_not_yet_available_from_features_and_targets(tmp_path) -> None:
    days = list(pd.bdate_range("2025-01-02", periods=40).date)
    service, market = builder(tmp_path, days)
    asset = make_bars("AAPL", days)
    asset[-1] = asset[-1].model_copy(update={
        "available_at": datetime(2099, 1, 1, tzinfo=timezone.utc),
        "ingested_at": datetime(2025, 3, 1, tzinfo=timezone.utc),
    })
    persist_bars(market, asset)
    persist_bars(market, make_bars("SPY", days))

    result = service.build(["AAPL"], days[0], days[-1], with_targets=True, persist=False)

    assert days[-1] not in set(result.features["decision_date"])
    assert days[-1] not in set(result.targets["decision_date"])
