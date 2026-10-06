from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from investment_system.core.exceptions import DataSourceError
from investment_system.data.full_universe import FullUniverseBuild, FullUniverseRequest
from investment_system.data.ingestion import IngestionSummary
from investment_system.data.normalization import extract_corporate_actions
from investment_system.data.schemas.market import MarketBar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.universe import UniverseConfig
from investment_system.features.store_builder import QuantitativeFeatureStoreBuilder


class WeekdayCalendar:
    def is_session(self, value: date) -> bool:
        return value.weekday() < 5

    def previous_session(self, value: date) -> date:
        value -= timedelta(days=1)
        while not self.is_session(value): value -= timedelta(days=1)
        return value

    def next_session(self, value: date) -> date:
        value += timedelta(days=1)
        while not self.is_session(value): value += timedelta(days=1)
        return value

    def session_open(self, value: date) -> datetime:
        return datetime.combine(value, time(14, 30), timezone.utc)

    def session_close(self, value: date) -> datetime:
        return datetime.combine(value, time(21), timezone.utc)


def universe() -> UniverseConfig:
    return UniverseConfig.model_validate({
        "benchmark": "SPY", "asset_class": "US_EQUITY", "universe_type": "development_fixed",
        "description": "fixture", "universe": {"name": "fixture", "point_in_time": False,
        "survivorship_bias_warning": True, "as_of": "2025-01-01"},
        "tickers": ["AAPL", "NEW", "EMPTY", "BAD"],
    })


def bars(ticker: str, days: list[date], split_day: date | None = None) -> list[MarketBar]:
    result = []
    for index, day in enumerate(days):
        split = 2.0 if day == split_day else 1.0
        base = 100 + index * .1 + (index % 7) * .02
        price = base / 2 if split_day and day >= split_day else base
        available = datetime.combine(day, time(20), ZoneInfo("America/New_York"))
        result.append(MarketBar(
            ticker=ticker, trading_date=day, provider="fixture", open=price * .999,
            high=price * 1.01, low=price * .99, close=price, volume=1_000_000 + index,
            split_factor=split, observed_at=available - timedelta(hours=4),
            available_at=available, ingested_at=available,
        ))
    return result


def persist(store: MarketDataStore, values: list[MarketBar]) -> None:
    store.upsert_bars(values)
    store.replace_actions_for_dates(values[0].ticker, {bar.trading_date for bar in values}, extract_corporate_actions(values))


class FakeIngestion:
    throttle_seconds = 0.0

    def __init__(self, store: MarketDataStore) -> None:
        self.store = store

    def ingest_ticker(self, ticker: str, start: date, end: date) -> IngestionSummary:
        if ticker == "BAD":
            raise DataSourceError("fixture provider error token=must-not-leak")
        count = len(self.store.read_bars(ticker))
        return IngestionSummary(ticker, start, start, end, count, count, 0, count, (), ())


def test_full_universe_orchestration_is_resilient_and_builds_rankings(tmp_path) -> None:
    days = list(pd.bdate_range("2023-01-02", periods=280).date)
    calendar = WeekdayCalendar()
    market = MarketDataStore(tmp_path / "raw", tmp_path / "processed")
    feature_store = QuantitativeFeatureStore(tmp_path / "features", tmp_path / "targets")
    persist(market, bars("SPY", days))
    persist(market, bars("AAPL", days, split_day=days[260]))
    persist(market, bars("NEW", days[-100:]))
    configured = universe()
    builder = QuantitativeFeatureStoreBuilder(
        market, feature_store, calendar, configured, raw_history_start=days[0],
        feature_history_start=days[0], minimum_rank_assets=2,
    )
    report_path = tmp_path / "reports" / "full.json"
    workflow = FullUniverseBuild(
        market, feature_store, calendar, configured, builder, report_path, FakeIngestion(market),
    )

    report = workflow.run(FullUniverseRequest(days[0], days[0], days[-1], True))

    assert report_path.exists()
    assert report["status"] == "completed_with_ticker_errors"
    assert report["global_summary"]["status_counts"] == {
        "success": 1, "no_data": 1, "partial_history": 1,
        "provider_error": 1, "validation_error": 0,
    }
    assert report["tickers"]["NEW"]["status"] == "partial_history"
    assert report["tickers"]["EMPTY"]["status"] == "no_data"
    assert report["tickers"]["BAD"]["status"] == "provider_error"
    assert "must-not-leak" not in report["tickers"]["BAD"]["error"]["message"]
    assert report["universe"]["universe_point_in_time"] is False
    assert report["universe"]["survivorship_bias_warning"] is True
    assert report["ranking_coverage"]["valid_rank_rows"] > 0
    assert report["ranking_coverage"]["rank_min"] == 0.0
    assert report["ranking_coverage"]["rank_max"] == 1.0
    assert report["cross_sectional_coverage"]["assets_with_features"]["max"] == 2
    assert report["global_summary"]["raw_bars"] == 660
    assert report["split_validation"]["failed"] == []
    assert "corporate_action_integrity" in report
    assert "number_of_detected_complex_events" in report["global_summary"]
    assert "expected_warmup_nans" in report
    assert "unresolved_provider_symbol_issues" in report

    resumed = workflow.run(
        FullUniverseRequest(days[0], days[0], days[-1], True),
        skip_features=True, skip_provider_tickers={"BAD"},
    )
    assert resumed["tickers"]["BAD"]["error"]["type"] == "ProviderTickerSkipped"
    assert resumed["universe"]["provider_tickers_explicitly_skipped"] == ["BAD"]
