from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timezone
from bisect import bisect_left
from time import perf_counter
from typing import Any
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from investment_system.data.calendar import TradingCalendar
from investment_system.data.normalization import AS_OF_VERSION, build_split_adjusted_series_as_of
from investment_system.data.schemas.features import QUANTITATIVE_FEATURE_COLUMNS
from investment_system.data.corporate_actions import add_feature_contamination_flags
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.universe import UniverseConfig
from investment_system.core.reproducibility import git_metadata
from investment_system.features.quantitative import build_quantitative_features
from investment_system.features.targets import (
    TARGET_COLUMNS,
    TARGET_METADATA_COLUMNS,
    add_cross_sectional_rank,
    build_price_targets,
)
from investment_system.features.validation import validate_quantitative_feature_frame, validate_target_frame

ESSENTIAL_FEATURES = (
    "return_60d", "momentum_120d", "volatility_60d", "rsi_14", "atr_pct",
    "distance_ma200", "volume_ratio_20d", "max_drawdown_60d", "spy_return_20d",
    "correlation_spy_20d", "beta_20d",
)

@dataclass(frozen=True)
class FeatureBuildResult:
    features: pd.DataFrame
    targets: pd.DataFrame | None
    manifest: dict[str, Any]
    report: dict[str, Any]

def _clock(value: str) -> time:
    return time.fromisoformat(value)

class QuantitativeFeatureStoreBuilder:
    """Build point-in-time quantitative rows from raw bars and corporate actions."""

    def __init__(
        self,
        market_store: MarketDataStore,
        feature_store: QuantitativeFeatureStore,
        calendar: TradingCalendar,
        universe: UniverseConfig,
        *,
        market_timezone: str = "America/New_York",
        decision_cutoff: str = "20:15",
        raw_history_start: date = date(2009, 1, 1),
        feature_history_start: date = date(2010, 1, 1),
        feature_schema_version: str = "3",
        quantitative_feature_version: str = "quantitative-v1.1",
        target_version: str = "corporate-action-safe-target-v3",
        minimum_rank_assets: int = 20,
    ) -> None:
        self.market_store = market_store
        self.feature_store = feature_store
        self.calendar = calendar
        self.universe = universe
        self.timezone = ZoneInfo(market_timezone)
        self.cutoff = _clock(decision_cutoff)
        self.raw_history_start = raw_history_start
        self.feature_history_start = feature_history_start
        self.feature_schema_version = feature_schema_version
        self.quantitative_feature_version = quantitative_feature_version
        self.target_version = target_version
        self.minimum_rank_assets = minimum_rank_assets

    def decision_time(self, day: date) -> datetime:
        return datetime.combine(day, self.cutoff, self.timezone)

    @staticmethod
    def _split_signature(actions: pd.DataFrame, day: date, decision_time: datetime) -> tuple[tuple[Any, ...], ...]:
        if actions.empty:
            return ()
        action_type = actions["action_type"].astype(str).str.lower()
        effective = pd.to_datetime(actions["effective_date"]).dt.date
        available = pd.to_datetime(actions["available_at"], utc=True, errors="coerce")
        cutoff = pd.Timestamp(decision_time).tz_convert("UTC")
        eligible = actions[action_type.str.endswith("split") & (effective <= day) & available.notna() & (available <= cutoff)]
        return tuple(sorted((str(row.effective_date), str(row.provider), float(row.split_factor)) for row in eligible.itertuples()))

    def _late_bar_signature(self, raw: pd.DataFrame, day: date, decision_time: datetime) -> tuple[tuple[str, str], ...]:
        """Identify past bars that became known only after their own cutoff."""
        if raw.empty:
            return ()
        trading_dates = pd.to_datetime(raw["trading_date"]).dt.date
        available = pd.to_datetime(raw["available_at"], utc=True, errors="coerce")
        own_cutoffs = pd.Series(
            [pd.Timestamp(self.decision_time(value)).tz_convert("UTC") for value in trading_dates],
            index=raw.index,
        )
        current_cutoff = pd.Timestamp(decision_time).tz_convert("UTC")
        eligible = raw[
            (trading_dates <= day)
            & available.notna()
            & (available <= current_cutoff)
            & (available > own_cutoffs)
        ]
        return tuple(sorted((str(row.trading_date), str(row.available_at)) for row in eligible.itertuples()))

    def _segments(self, days: list[date], asset_actions: pd.DataFrame, benchmark_actions: pd.DataFrame, asset_raw: pd.DataFrame, benchmark_raw: pd.DataFrame) -> list[list[date]]:
        """Group days by causal inputs, using activation events instead of O(days*rows) rescans."""
        decision_cutoffs = [pd.Timestamp(self.decision_time(day)).tz_convert("UTC") for day in days]

        def activations(frame: pd.DataFrame, *, actions: bool) -> dict[date, list[tuple[Any, ...]]]:
            events: dict[date, list[tuple[Any, ...]]] = {}
            if frame.empty:
                return events
            for row in frame.itertuples(index=False):
                effective = pd.Timestamp(row.effective_date if actions else row.trading_date).date()
                available = pd.to_datetime(row.available_at, utc=True, errors="coerce")
                if pd.isna(available):
                    continue
                if actions:
                    if not str(row.action_type).lower().endswith("split"):
                        continue
                    payload = (str(row.effective_date), str(row.provider), float(row.split_factor))
                else:
                    own_cutoff = pd.Timestamp(self.decision_time(effective)).tz_convert("UTC")
                    if available <= own_cutoff:
                        continue
                    payload = (str(row.trading_date), str(row.available_at))
                index = max(bisect_left(days, effective), bisect_left(decision_cutoffs, available))
                if index < len(days):
                    events.setdefault(days[index], []).append(payload)
            return events

        event_sets = (
            activations(asset_actions, actions=True),
            activations(benchmark_actions, actions=True),
            activations(asset_raw, actions=False),
            activations(benchmark_raw, actions=False),
        )
        active: tuple[set[tuple[Any, ...]], ...] = (set(), set(), set(), set())
        segments: list[list[date]] = []
        signature: tuple[Any, ...] | None = None
        for day in days:
            for state, events in zip(active, event_sets):
                state.update(events.get(day, ()))
            current = tuple(tuple(sorted(state)) for state in active)
            if current != signature:
                segments.append([])
                signature = current
            segments[-1].append(day)
        return segments

    def _history_count(self, raw: pd.DataFrame, day: date) -> int:
        trading_dates = pd.to_datetime(raw["trading_date"]).dt.date
        available = pd.to_datetime(raw["available_at"], utc=True, errors="coerce")
        cutoff = pd.Timestamp(self.decision_time(day)).tz_convert("UTC")
        return int(((trading_dates <= day) & available.notna() & (available <= cutoff)).sum())

    def _history_counts(self, raw: pd.DataFrame, days: list[date]) -> list[int]:
        """Return the same causal counts as ``_history_count`` in linear-event form."""
        events = [0] * len(days)
        decision_cutoffs = [pd.Timestamp(self.decision_time(day)).tz_convert("UTC") for day in days]
        for row in raw.itertuples(index=False):
            trading_day = pd.Timestamp(row.trading_date).date()
            available = pd.to_datetime(row.available_at, utc=True, errors="coerce")
            if pd.isna(available):
                continue
            index = max(bisect_left(days, trading_day), bisect_left(decision_cutoffs, available))
            if index < len(days):
                events[index] += 1
        total = 0
        result: list[int] = []
        for increment in events:
            total += increment
            result.append(total)
        return result

    def build_ticker(self, ticker: str, start_date: date, end_date: date, benchmark_raw: pd.DataFrame, benchmark_actions: pd.DataFrame) -> pd.DataFrame:
        raw = self.market_store.read_bars(ticker)
        actions = self.market_store.read_actions(ticker)
        if raw.empty:
            return pd.DataFrame()
        raw = raw[pd.to_datetime(raw["trading_date"]).dt.date >= self.raw_history_start].copy()
        raw_dates = pd.to_datetime(raw["trading_date"]).dt.date
        available = pd.to_datetime(raw["available_at"], utc=True, errors="coerce")
        candidate_days = sorted({day for day, known in zip(raw_dates, available.notna()) if known and start_date <= day <= end_date and self.calendar.is_session(day)})
        if not candidate_days:
            return pd.DataFrame()
        pieces: list[pd.DataFrame] = []
        for segment in self._segments(candidate_days, actions, benchmark_actions, raw, benchmark_raw):
            segment_end = segment[-1]
            cutoff = self.decision_time(segment_end)
            asset_view = build_split_adjusted_series_as_of(raw, actions, decision_date=segment_end, decision_time=cutoff)
            benchmark_view = build_split_adjusted_series_as_of(benchmark_raw, benchmark_actions, decision_date=segment_end, decision_time=cutoff)
            if benchmark_view.empty:
                raise ValueError(f"benchmark has no point-in-time data by {segment_end}")
            asset_view = asset_view.set_index("trading_date", drop=False).sort_index()
            benchmark_close = benchmark_view.set_index("trading_date")["split_adjusted_close"].sort_index()
            if asset_view.index.intersection(benchmark_close.index).empty:
                raise ValueError(f"benchmark has no dates overlapping {ticker}")
            calculated = build_quantitative_features(asset_view, benchmark_close)
            pieces.append(calculated.loc[calculated.index.intersection(segment)].copy())
        frame = pd.concat(pieces).sort_index()
        frame["history_count"] = self._history_counts(raw, list(frame.index))
        frame["ticker"] = ticker
        frame["decision_date"] = frame.index
        frame["decision_time"] = [self.decision_time(day) for day in frame.index]
        frame["sector"] = None
        frame["industry"] = None
        frame["market_cap"] = np.nan
        for sessions in (20, 60, 120, 252):
            frame[f"has_{sessions}d_history"] = frame["history_count"] >= sessions
        frame["model_eligible"] = (frame["history_count"] > 252) & frame[list(ESSENTIAL_FEATURES)].notna().all(axis=1)
        for column in ("sector_return_5d", "sector_return_20d", "relative_sector_return_20d"):
            frame[column] = np.nan
        output_columns = [
            "ticker", "decision_date", "decision_time", "sector", "industry", "market_cap",
            "history_count",
            "has_20d_history", "has_60d_history", "has_120d_history", "has_252d_history", "model_eligible",
            *QUANTITATIVE_FEATURE_COLUMNS,
        ]
        result = frame.reindex(columns=output_columns).replace([np.inf, -np.inf], np.nan).reset_index(drop=True)
        events = self.market_store.read_corporate_action_events()
        if not events.empty:
            events = events[events["ticker"] == ticker]
        result = add_feature_contamination_flags(result, events, self.calendar)
        validate_quantitative_feature_frame(result)
        return result

    def build(
        self, tickers: list[str], start_date: date, end_date: date, *,
        with_targets: bool = False, persist: bool = True,
        continue_on_ticker_error: bool = False,
    ) -> FeatureBuildResult:
        if start_date < self.feature_history_start:
            start_date = self.feature_history_start
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")
        known_at = datetime.now(timezone.utc)
        benchmark_raw = self.market_store.read_bars(self.universe.benchmark)
        benchmark_actions = self.market_store.read_actions(self.universe.benchmark)
        if benchmark_raw.empty:
            raise ValueError(f"benchmark data is required: {self.universe.benchmark}")
        benchmark_raw = benchmark_raw[pd.to_datetime(benchmark_raw["trading_date"]).dt.date >= self.raw_history_start].copy()
        feature_frames: list[pd.DataFrame] = []
        target_frames: list[pd.DataFrame] = []
        missing_tickers: list[str] = []
        build_seconds_by_ticker: dict[str, float] = {}
        target_seconds_by_ticker: dict[str, float] = {}
        ticker_errors: dict[str, dict[str, str]] = {}
        for ticker in tickers:
            started = perf_counter()
            try:
                frame = self.build_ticker(ticker, start_date, end_date, benchmark_raw, benchmark_actions)
            except ValueError as error:
                build_seconds_by_ticker[ticker] = perf_counter() - started
                if not continue_on_ticker_error:
                    raise
                ticker_errors[ticker] = {"stage": "features", "type": type(error).__name__, "message": str(error)}
                missing_tickers.append(ticker)
                continue
            build_seconds_by_ticker[ticker] = perf_counter() - started
            if frame.empty:
                missing_tickers.append(ticker)
                continue
            feature_frames.append(frame)
            if with_targets:
                target_started = perf_counter()
                try:
                    target_bars = self.market_store.read_bars(ticker)
                    target_actions = self.market_store.read_actions(ticker)
                    if not target_bars.empty:
                        bar_availability = pd.to_datetime(target_bars["available_at"], utc=True, errors="coerce")
                        target_bars = target_bars[bar_availability.notna() & (bar_availability <= known_at)]
                    if not target_actions.empty:
                        action_availability = pd.to_datetime(target_actions["available_at"], utc=True, errors="coerce")
                        target_actions = target_actions[action_availability.notna() & (action_availability <= known_at)]
                    events = self.market_store.read_corporate_action_events()
                    if not events.empty:
                        events = events[events["ticker"] == ticker]
                    targets = build_price_targets(target_bars, target_actions, self.calendar, events)
                    dates = pd.to_datetime(targets["decision_date"]).dt.date
                    target_frames.append(targets[(dates >= start_date) & (dates <= end_date)])
                except ValueError as error:
                    if not continue_on_ticker_error:
                        raise
                    ticker_errors[ticker] = {"stage": "targets", "type": type(error).__name__, "message": str(error)}
                finally:
                    target_seconds_by_ticker[ticker] = perf_counter() - target_started
        features = pd.concat(feature_frames, ignore_index=True) if feature_frames else pd.DataFrame()
        if not features.empty:
            validate_quantitative_feature_frame(features)
        targets: pd.DataFrame | None = None
        if with_targets:
            targets = pd.concat(target_frames, ignore_index=True) if target_frames else pd.DataFrame(columns=["ticker", "decision_date"])
            targets = add_cross_sectional_rank(targets, self.minimum_rank_assets)
            validate_target_frame(targets)
        manifest = self._manifest(tickers, start_date, end_date, known_at, with_targets)
        report = self._report(features, missing_tickers)
        report["feature_build_seconds_by_ticker"] = build_seconds_by_ticker
        report["target_build_seconds_by_ticker"] = target_seconds_by_ticker
        report["ticker_errors"] = ticker_errors
        if persist:
            self.feature_store.replace_feature_range(features, tickers, start_date, end_date)
            if targets is not None:
                self.feature_store.replace_target_range(targets, tickers, start_date, end_date)
            self.feature_store.write_manifest(manifest)
            self.feature_store.write_report(report)
        return FeatureBuildResult(features, targets, manifest, report)

    def _manifest(self, tickers: list[str], start: date, end: date, built_at: datetime, with_targets: bool) -> dict[str, Any]:
        return {
            "manifest_schema_version": "1",
            "generated_at": built_at.isoformat(),
            **git_metadata(),
            "feature_schema_version": self.feature_schema_version,
            "quantitative_feature_version": self.quantitative_feature_version,
            "target_version": self.target_version,
            "target_schema_version": self.target_version,
            "target_columns": list(TARGET_COLUMNS),
            "target_metadata_columns": list(TARGET_METADATA_COLUMNS),
            "normalization_version": AS_OF_VERSION,
            "universe_name": self.universe.universe.name,
            "universe_as_of": self.universe.universe.as_of,
            "universe_point_in_time": self.universe.universe.point_in_time,
            "survivorship_bias_warning": self.universe.universe.survivorship_bias_warning,
            "benchmark": self.universe.benchmark,
            "raw_history_start": self.raw_history_start,
            "feature_history_start": self.feature_history_start,
            "requested_start": start,
            "requested_end": end,
            "build_timestamp": built_at,
            "source_provider": "tiingo",
            "tickers": tickers,
            "targets_built": with_targets,
            "settings": {
                "market_timezone": str(self.timezone),
                "decision_cutoff": self.cutoff.isoformat(timespec="minutes"),
                "minimum_rank_assets": self.minimum_rank_assets,
            },
        }

    def _report(self, features: pd.DataFrame, missing_tickers: list[str]) -> dict[str, Any]:
        if features.empty:
            return {"tickers": 0, "rows": 0, "missing_tickers": missing_tickers, "duplicates": 0, "infinities": 0}
        numeric = features.select_dtypes(include=[np.number])
        relevant = [name for name in ("return_10d", "volatility_20d", "rsi_14", "atr_pct", "beta_60d") if name in numeric]
        gaps: dict[str, list[str]] = {}
        for ticker, group in features.groupby("ticker"):
            present = set(pd.to_datetime(group["decision_date"]).dt.date)
            cursor, last = min(present), max(present)
            missing: list[str] = []
            while cursor <= last:
                if self.calendar.is_session(cursor) and cursor not in present:
                    missing.append(cursor.isoformat())
                cursor = date.fromordinal(cursor.toordinal() + 1)
            if missing:
                gaps[ticker] = missing
        return {
            "tickers": int(features["ticker"].nunique()),
            "date_min": str(features["decision_date"].min()),
            "date_max": str(features["decision_date"].max()),
            "rows": int(len(features)),
            "nan_percentage": {column: float(features[column].isna().mean() * 100) for column in QUANTITATIVE_FEATURE_COLUMNS},
            "model_eligible_rows": int(features["model_eligible"].sum()),
            "missing_tickers": missing_tickers,
            "gaps_detected": gaps,
            "min_max": {column: {"min": float(numeric[column].min()) if numeric[column].notna().any() else None, "max": float(numeric[column].max()) if numeric[column].notna().any() else None} for column in relevant},
            "duplicates": int(features.duplicated(["ticker", "decision_date"]).sum()),
            "infinities": int(np.isinf(numeric.to_numpy()).sum()),
        }
