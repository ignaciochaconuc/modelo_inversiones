"""Diagnostic synthetic benchmark for Phase 1C; intentionally excluded from pytest."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
from zoneinfo import ZoneInfo

import pandas as pd

from investment_system.data.normalization import build_split_adjusted_series_as_of, extract_corporate_actions
from investment_system.data.schemas.market import MarketBar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.universe import UniverseConfig
from investment_system.features.quantitative import build_quantitative_features
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


def make_bars(ticker: str, days: list[date], split_indices: set[int], delayed: dict[int, int]) -> list[MarketBar]:
    bars: list[MarketBar] = []
    cumulative = 1.0
    for index, day in enumerate(days):
        split = 2.0 if index in split_indices else 1.0
        if split != 1:
            cumulative *= split
        price = (80 + index * .025 + (index % 17) * .03) / cumulative
        available_day = days[delayed[index]] if index in delayed else day
        available = datetime.combine(available_day, time(20), ZoneInfo("America/New_York"))
        bars.append(MarketBar(
            ticker=ticker, trading_date=day, provider="synthetic", open=price * .999,
            high=price * 1.01, low=price * .99, close=price, volume=1_000_000 + index,
            split_factor=split, observed_at=datetime.combine(day, time(16), ZoneInfo("America/New_York")),
            available_at=available, ingested_at=available,
        ))
    return bars


def persist(store: MarketDataStore, bars: list[MarketBar]) -> None:
    store.upsert_bars(bars)
    store.replace_actions_for_dates(bars[0].ticker, {bar.trading_date for bar in bars}, extract_corporate_actions(bars))


def main() -> int:
    days = list(pd.bdate_range("2009-01-02", periods=4500).date)
    universe = UniverseConfig.model_validate({
        "benchmark": "SPY", "asset_class": "US_EQUITY", "universe_type": "benchmark",
        "description": "synthetic benchmark", "universe": {"name": "synthetic", "point_in_time": False,
        "survivorship_bias_warning": True, "as_of": str(days[-1])}, "tickers": ["TEST"],
    })
    with TemporaryDirectory(prefix="feature-builder-benchmark-") as temporary:
        root = Path(temporary)
        market = MarketDataStore(root / "raw", root / "processed")
        feature_store = QuantitativeFeatureStore(root / "features", root / "targets")
        persist(market, make_bars("SPY", days, set(), {700: 705}))
        persist(market, make_bars("TEST", days, {1200, 2600, 3900}, {500: 510, 3000: 3015}))
        builder = QuantitativeFeatureStoreBuilder(
            market, feature_store, WeekdayCalendar(), universe,
            raw_history_start=days[0], feature_history_start=days[0],
        )
        raw, actions = market.read_bars("TEST"), market.read_actions("TEST")
        benchmark_raw, benchmark_actions = market.read_bars("SPY"), market.read_actions("SPY")

        started = perf_counter()
        segments = builder._segments(days, actions, benchmark_actions, raw, benchmark_raw)
        segment_seconds = perf_counter() - started

        started = perf_counter()
        cutoff = builder.decision_time(days[-1])
        view = build_split_adjusted_series_as_of(raw, actions, decision_date=days[-1], decision_time=cutoff)
        benchmark_view = build_split_adjusted_series_as_of(
            benchmark_raw, benchmark_actions, decision_date=days[-1], decision_time=cutoff,
        )
        build_quantitative_features(
            view.set_index("trading_date", drop=False),
            benchmark_view.set_index("trading_date")["split_adjusted_close"],
        )
        calculation_seconds = perf_counter() - started

        started = perf_counter()
        result = builder.build_ticker("TEST", days[0], days[-1], benchmark_raw, benchmark_actions)
        total_seconds = perf_counter() - started
        print(f"sessions={len(days)} segments={len(segments)} rows={len(result)}")
        print(f"segment_creation_seconds={segment_seconds:.3f}")
        print(f"representative_feature_calculation_seconds={calculation_seconds:.3f}")
        print(f"total_build_seconds={total_seconds:.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
