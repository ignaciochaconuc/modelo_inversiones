from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

import pandas as pd

from investment_system.data.normalization import extract_corporate_actions
from investment_system.data.pilot import PilotRequest, RealDataPilot
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
        while not self.is_session(value):
            value -= timedelta(days=1)
        return value

    def next_session(self, value: date) -> date:
        value += timedelta(days=1)
        while not self.is_session(value):
            value += timedelta(days=1)
        return value

    def session_open(self, value: date) -> datetime:
        return datetime.combine(value, time(14, 30), timezone.utc)

    def session_close(self, value: date) -> datetime:
        return datetime.combine(value, time(21), timezone.utc)


def _universe() -> UniverseConfig:
    return UniverseConfig.model_validate({
        "benchmark": "SPY", "asset_class": "US_EQUITY", "universe_type": "pilot",
        "description": "fixture", "universe": {"name": "pilot", "point_in_time": False,
        "survivorship_bias_warning": True, "as_of": "2025-01-01"}, "tickers": ["AAPL"],
    })


def _bars(ticker: str, days: list[date], split_day: date | None = None) -> list[MarketBar]:
    result = []
    for index, day in enumerate(days):
        split = 2.0 if day == split_day else 1.0
        unsplit = 80 + index * .15 + (index % 11) * .03
        price = unsplit / 2 if split_day and day >= split_day else unsplit
        available = datetime.combine(day, time(20), ZoneInfo("America/New_York"))
        result.append(MarketBar(
            ticker=ticker, trading_date=day, provider="tiingo", open=price * .999,
            high=price * 1.01, low=price * .99, close=price, volume=1_000_000 + index,
            split_factor=split, observed_at=available - timedelta(hours=4),
            available_at=available, ingested_at=available,
        ))
    return result


def _persist(store: MarketDataStore, bars: list[MarketBar]) -> None:
    store.upsert_bars(bars)
    store.replace_actions_for_dates(
        bars[0].ticker, {bar.trading_date for bar in bars}, extract_corporate_actions(bars)
    )


def test_pilot_builds_offline_report_with_pit_and_split_evidence(tmp_path) -> None:
    days = list(pd.bdate_range("2023-01-02", periods=280).date)
    calendar = WeekdayCalendar()
    market = MarketDataStore(tmp_path / "raw", tmp_path / "processed")
    features = QuantitativeFeatureStore(tmp_path / "features", tmp_path / "targets")
    _persist(market, _bars("SPY", days))
    _persist(market, _bars("AAPL", days, split_day=days[260]))
    builder = QuantitativeFeatureStoreBuilder(
        market, features, calendar, _universe(), raw_history_start=days[0],
        feature_history_start=days[0], minimum_rank_assets=20,
    )
    report_path = tmp_path / "reports" / "real_data_pilot.json"
    pilot = RealDataPilot(market, features, calendar, builder, report_path)
    request = PilotRequest(days[0], days[0], days[-1], ("AAPL",), "SPY", True)

    report = pilot.run(request, skip_download=True)

    assert report_path.exists()
    assert report["status"] == "passed"
    assert report["point_in_time"]["passed"]
    assert report["raw_by_ticker"]["AAPL"]["split_count"] == 1
    assert len(report["split_windows"]["AAPL"][0]["rows"]) == 7
    assert report["features_by_ticker"]["AAPL"]["first_model_eligible"] is not None
    assert report["targets"]["rank_all_nan_expected_small_universe"]
    assert report["targets"]["horizons"]["20"]["trailing_nan"]


def test_pilot_request_includes_benchmark_once() -> None:
    request = PilotRequest(date(2009, 1, 1), date(2010, 1, 1), date(2011, 1, 1),
                           ("AAPL", "SPY", "AAPL"), "SPY")
    assert request.all_tickers == ("SPY", "AAPL")
