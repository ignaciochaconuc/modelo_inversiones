"""Resilient Phase 1D orchestration and diagnostics for the fixed development universe."""
from __future__ import annotations

import json
import re
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd
from pydantic import ValidationError

from investment_system.core.exceptions import DataQualityError, DataSourceError, DataSourceRateLimitError
from investment_system.core.reproducibility import git_metadata
from investment_system.data.calendar import TradingCalendar
from investment_system.data.ingestion import MarketDataIngestionService
from investment_system.data.normalization import AS_OF_VERSION, build_split_adjusted_series_as_of
from investment_system.data.schemas.features import QUANTITATIVE_FEATURE_COLUMNS
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.universe import UniverseConfig
from investment_system.features.store_builder import QuantitativeFeatureStoreBuilder

REPORT_SCHEMA_VERSION = "1"
DELIBERATE_NULL_FEATURES = {
    "sector_return_5d", "sector_return_20d", "relative_sector_return_20d",
}


@dataclass(frozen=True)
class FullUniverseRequest:
    raw_start: date
    feature_start: date
    end: date
    with_targets: bool = True


def _dates(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_datetime(frame[column]).dt.date


def _json_default(value: Any) -> Any:
    if value is pd.NA:
        return None
    if isinstance(value, (datetime, date, pd.Timestamp)):
        return value.isoformat()
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def _safe_error(error: BaseException) -> str:
    message = str(error).replace("\r", " ").replace("\n", " ")[:500]
    return re.sub(
        r"(?i)(authorization|token|api[_-]?key)(\s*[:=]\s*|\s+)[^\s,;]+",
        r"\1\2[REDACTED]", message,
    )


class FullUniverseBuild:
    """Use the existing ingestion and feature pipeline with per-ticker recovery."""

    def __init__(
        self,
        market_store: MarketDataStore,
        feature_store: QuantitativeFeatureStore,
        calendar: TradingCalendar,
        universe: UniverseConfig,
        builder: QuantitativeFeatureStoreBuilder,
        report_path: str | Path,
        ingestion: MarketDataIngestionService | None = None,
        settings_metadata: dict[str, Any] | None = None,
    ) -> None:
        self.market_store = market_store
        self.feature_store = feature_store
        self.calendar = calendar
        self.universe = universe
        self.builder = builder
        self.report_path = Path(report_path)
        self.ingestion = ingestion
        self.settings_metadata = settings_metadata or {}

    def run(
        self, request: FullUniverseRequest, *, skip_download: bool = False,
        skip_features: bool = False, skip_provider_tickers: set[str] | None = None,
    ) -> dict[str, Any]:
        if request.raw_start > request.feature_start or request.feature_start > request.end:
            raise ValueError("expected raw_start <= feature_start <= end")
        started = perf_counter()
        skip_provider_tickers = {ticker.upper() for ticker in (skip_provider_tickers or set())}
        previous: dict[str, Any] = {}
        if self.report_path.exists():
            try:
                previous = json.loads(self.report_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                previous = {}
        self._requested_sessions = self._sessions(request.raw_start, request.end)
        now = datetime.now(timezone.utc)
        completed_sessions = [day for day in self._requested_sessions
                              if self.builder.decision_time(day).astimezone(timezone.utc) <= now]
        required_last_session = max(completed_sessions) if completed_sessions else None
        if required_last_session is None or request.feature_start > required_last_session:
            raise ValueError("no completed decision session exists in the requested feature range")
        all_market_tickers = list(dict.fromkeys((self.universe.benchmark, *self.universe.tickers)))
        states = {ticker: {"status": "success", "warnings": [], "error": None,
                           "ingestion_seconds": 0.0, "ingestion_succeeded": False}
                  for ticker in all_market_tickers}
        if skip_download:
            for ticker in all_market_tickers:
                states[ticker]["ingestion_succeeded"] = not self.market_store.read_bars(ticker).empty
                previous_item = (previous.get("tickers", {}).get(ticker)
                                 if ticker != self.universe.benchmark else previous.get("benchmark")) or {}
                if not states[ticker]["ingestion_succeeded"] and previous_item.get("status") == "provider_error":
                    states[ticker].update(status="provider_error", error=previous_item.get("error"))
        ingestion_started = perf_counter()
        if not skip_download:
            if self.ingestion is None:
                raise ValueError("ingestion service is required unless --skip-download is used")
            rate_limited = False
            for index, ticker in enumerate(all_market_tickers):
                latest = self.market_store.latest_trading_date(ticker)
                if required_last_session is not None and latest is not None and latest >= required_last_session:
                    states[ticker]["ingestion_succeeded"] = True
                    states[ticker]["ingestion_skipped_up_to_date"] = True
                    states[ticker]["warnings"].append("ingestion skipped: local data reaches latest completed session")
                    continue
                previous_item = (previous.get("tickers", {}).get(ticker)
                                 if ticker != self.universe.benchmark else previous.get("benchmark")) or {}
                previous_error = previous_item.get("error") or {}
                if ticker in skip_provider_tickers:
                    states[ticker].update(status="provider_error", error={
                        "type": "ProviderTickerSkipped",
                        "message": "provider request explicitly skipped after manual review",
                    })
                    states[ticker]["warnings"].append("provider request skipped explicitly; no ticker mapping was inferred")
                    continue
                if latest is not None and previous_item.get("unexpected_missing_sessions"):
                    states[ticker]["status"] = "partial_history"
                    states[ticker]["ingestion_succeeded"] = True
                    states[ticker]["warnings"].append("ingestion skipped: known incomplete provider history requires review")
                    continue
                if latest is None and previous_item.get("status") == "provider_error" and "HTTP 404" in previous_error.get("message", ""):
                    states[ticker].update(status="provider_error", error=previous_error)
                    states[ticker]["warnings"].append("ingestion skipped: previous permanent provider 404")
                    continue
                if rate_limited:
                    states[ticker].update(status="provider_error", error={
                        "type": "DataSourceRateLimitError",
                        "message": "not attempted after provider rate limit",
                    })
                    continue
                step = perf_counter()
                try:
                    summary = self.ingestion.ingest_ticker(ticker, request.raw_start, request.end)
                    states[ticker]["ingestion"] = asdict(summary)
                    states[ticker]["ingestion_succeeded"] = True
                except DataSourceRateLimitError as error:
                    states[ticker].update(status="provider_error", error={"type": type(error).__name__, "message": _safe_error(error)})
                    rate_limited = True
                except DataSourceError as error:
                    states[ticker].update(status="provider_error", error={"type": type(error).__name__, "message": _safe_error(error)})
                except (DataQualityError, ValidationError, ValueError) as error:
                    states[ticker].update(status="validation_error", error={"type": type(error).__name__, "message": _safe_error(error)})
                finally:
                    states[ticker]["ingestion_seconds"] = perf_counter() - step
                if (not rate_limited and self.ingestion.throttle_seconds
                        and index < len(all_market_tickers) - 1):
                    time.sleep(self.ingestion.throttle_seconds)
        ingestion_wall_seconds = perf_counter() - ingestion_started

        for ticker in all_market_tickers:
            bars = self.market_store.read_bars(ticker)
            if bars.empty:
                if states[ticker]["status"] == "success":
                    states[ticker]["status"] = "no_data"
                continue
            first = _dates(bars, "trading_date").min()
            first_expected = self._requested_sessions[0]
            if first > first_expected and states[ticker]["status"] == "success":
                states[ticker]["status"] = "partial_history"
            if first > first_expected:
                states[ticker]["warnings"].append("history_starts_after_requested_period; review IPO/listing or ticker history")
            if states[ticker]["status"] in {"provider_error", "validation_error"}:
                states[ticker]["warnings"].append("build uses previously stored local data")

        if self.market_store.read_bars(self.universe.benchmark).empty:
            raise ValueError(f"benchmark data is required: {self.universe.benchmark}")
        build_tickers = [ticker for ticker in self.universe.tickers if not self.market_store.read_bars(ticker).empty]
        build_started = perf_counter()
        if skip_features:
            features = self.feature_store.read_features()
            if not features.empty:
                feature_dates = _dates(features, "decision_date")
                features = features[
                    features["ticker"].isin(self.universe.tickers)
                    & (feature_dates >= request.feature_start) & (feature_dates <= request.end)
                ].copy()
            targets = self.feature_store.read_targets() if request.with_targets else None
            if targets is not None and not targets.empty:
                target_dates = _dates(targets, "decision_date")
                targets = targets[
                    targets["ticker"].isin(self.universe.tickers)
                    & (target_dates >= request.feature_start) & (target_dates <= request.end)
                ].copy()
            build_report = {
                "feature_build_seconds_by_ticker": previous.get("performance", {}).get("feature_build_seconds_by_ticker", {}),
                "target_build_seconds_by_ticker": previous.get("performance", {}).get("target_build_seconds_by_ticker", {}),
                "ticker_errors": {},
            }
        else:
            result = self.builder.build(
                build_tickers, request.feature_start, required_last_session,
                with_targets=request.with_targets, persist=True, continue_on_ticker_error=True,
            )
            features, targets, build_report = result.features, result.targets, result.report
        build_wall_seconds = perf_counter() - build_started
        for ticker, error in build_report.get("ticker_errors", {}).items():
            states[ticker].update(status="validation_error", error={
                "type": error["type"], "message": _safe_error(ValueError(error["message"])), "stage": error["stage"],
            })

        validation_started = perf_counter()
        per_ticker = {
            ticker: self._ticker_report(ticker, request, states[ticker], features, targets, build_report)
            for ticker in self.universe.tickers
        }
        benchmark_report = self._ticker_report(
            self.universe.benchmark, request, states[self.universe.benchmark], features, targets, build_report,
        )
        cross_sectional = self._cross_sectional(features, targets)
        ranking = self._ranking_diagnostics(targets)
        unexpected_nans = self._unexpected_nans(features)
        outliers, extremes = self._outliers_and_extremes(features)
        split_validation = self._split_validation(all_market_tickers)
        validation_seconds = perf_counter() - validation_started
        sizes = self._dataset_sizes()
        status_counts = {name: sum(item["status"] == name for item in per_ticker.values())
                         for name in ("success", "no_data", "partial_history", "provider_error", "validation_error")}
        all_reports = [benchmark_report, *per_ticker.values()]
        actions_total = sum(item["split_count"] + item["dividend_count"] for item in all_reports)
        numeric = features.select_dtypes(include=[np.number]) if not features.empty else pd.DataFrame()
        report = {
            "phase": "1D-full-development-universe",
            "status": "completed_with_ticker_errors" if status_counts["provider_error"] + status_counts["validation_error"] else "passed",
            "reproducibility": {
                "report_schema_version": REPORT_SCHEMA_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                **git_metadata(),
                "feature_schema_version": self.builder.feature_schema_version,
                "quantitative_feature_version": self.builder.quantitative_feature_version,
                "normalization_version": AS_OF_VERSION,
                "provider": "tiingo",
                "settings": {
                    "raw_start": request.raw_start,
                    "feature_start": request.feature_start,
                    "end": request.end,
                    "effective_feature_end": required_last_session,
                    "market_timezone": str(self.builder.timezone),
                    "decision_cutoff": self.builder.cutoff.isoformat(timespec="minutes"),
                    "minimum_rank_assets": self.builder.minimum_rank_assets,
                    **self.settings_metadata,
                },
            },
            "universe": {
                "name": self.universe.universe.name,
                "type": self.universe.universe_type,
                "as_of": self.universe.universe.as_of,
                "benchmark": self.universe.benchmark,
                "configured_tickers": len(self.universe.tickers),
                "universe_point_in_time": self.universe.universe.point_in_time,
                "survivorship_bias_warning": self.universe.universe.survivorship_bias_warning,
                "provider_tickers_explicitly_skipped": sorted(skip_provider_tickers),
            },
            "global_summary": {
                "status_counts": status_counts,
                "tickers_downloaded_successfully": sum(bool(states[ticker]["ingestion_succeeded"]) for ticker in self.universe.tickers),
                "raw_bars": sum(item["raw_bars"] for item in all_reports),
                "corporate_actions": actions_total,
                "splits": sum(item["split_count"] for item in all_reports),
                "dividends": sum(item["dividend_count"] for item in all_reports),
                "feature_rows": int(len(features)),
                "model_eligible_rows": int(features["model_eligible"].sum()) if not features.empty else 0,
                "target_rows": int(len(targets)) if targets is not None else 0,
                "first_raw_date": min((item["first_raw_date"] for item in all_reports if item["first_raw_date"]), default=None),
                "last_raw_date": max((item["last_raw_date"] for item in all_reports if item["last_raw_date"]), default=None),
                "first_feature_date": min(_dates(features, "decision_date")) if not features.empty else None,
                "last_feature_date": max(_dates(features, "decision_date")) if not features.empty else None,
                "duplicates": sum(item["duplicates"] for item in all_reports),
                "ohlc_violations": sum(item["ohlc_violations"] for item in all_reports),
                "unexpected_gaps": sum(len(item["unexpected_missing_sessions"]) for item in all_reports),
                "infinities": int(np.isinf(numeric.to_numpy()).sum()) if not numeric.empty else 0,
                "unexpected_nan_cells_eligible": sum(item["count"] for item in unexpected_nans.values()),
                "raw_bars_not_yet_available": sum(item["raw_bars_not_yet_available"] for item in all_reports),
            },
            "benchmark": benchmark_report,
            "tickers": per_ticker,
            "possible_ticker_history_issue": [
                {"ticker": ticker, "first_available_date": item["first_raw_date"],
                 "requested_start": request.raw_start,
                 "calendar_days_after_requested": (item["first_raw_date"] - request.raw_start).days}
                for ticker, item in per_ticker.items()
                if item["status"] == "partial_history" and item["first_raw_date"]
            ],
            "cross_sectional_coverage": cross_sectional,
            "ranking_coverage": ranking,
            "unexpected_nans_eligible": unexpected_nans,
            "deliberate_null_fields": [
                "sector", "industry", "market_cap", "sector_return_5d",
                "sector_return_20d", "relative_sector_return_20d",
            ],
            "outliers_diagnostic_only": outliers,
            "extremes_top_25": extremes,
            "split_validation": split_validation,
            "performance": {
                "ingestion_seconds_by_ticker": {ticker: states[ticker]["ingestion_seconds"] for ticker in all_market_tickers},
                "feature_build_seconds_by_ticker": build_report.get("feature_build_seconds_by_ticker", {}),
                "target_build_seconds_by_ticker": build_report.get("target_build_seconds_by_ticker", {}),
                "ingestion_wall_seconds": ingestion_wall_seconds,
                "feature_and_target_build_wall_seconds": build_wall_seconds,
                "feature_build_seconds_sum": sum(build_report.get("feature_build_seconds_by_ticker", {}).values()),
                "target_build_seconds_sum": sum(build_report.get("target_build_seconds_by_ticker", {}).values()),
                "stages_skipped": {"download": skip_download, "features": skip_features},
                "validation_report_seconds": validation_seconds,
                "total_seconds": perf_counter() - started,
            },
            "dataset_sizes_bytes": sizes,
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.report_path.with_suffix(".tmp.json")
        temporary.write_text(json.dumps(report, indent=2, default=_json_default), encoding="utf-8")
        temporary.replace(self.report_path)
        return report

    def _sessions(self, start: date, end: date) -> list[date]:
        return [date.fromordinal(value) for value in range(start.toordinal(), end.toordinal() + 1)
                if self.calendar.is_session(date.fromordinal(value))]

    def _ticker_report(self, ticker: str, request: FullUniverseRequest, state: dict[str, Any],
                       features: pd.DataFrame, targets: pd.DataFrame | None,
                       build_report: dict[str, Any]) -> dict[str, Any]:
        bars, actions = self.market_store.read_bars(ticker), self.market_store.read_actions(ticker)
        group = features[features["ticker"] == ticker] if not features.empty else features
        target_group = targets[targets["ticker"] == ticker] if targets is not None and not targets.empty else pd.DataFrame()
        if bars.empty:
            return {"status": state["status"], "error": state["error"], "first_raw_date": None,
                    "last_raw_date": None, "raw_bars": 0, "expected_sessions_from_first_raw": 0,
                    "unexpected_missing_sessions": [], "pending_sessions_before_cutoff": [],
                    "raw_bars_not_yet_available": 0,
                    "split_count": 0, "split_dates": [], "dividend_count": 0, "dividend_date_examples": [],
                    "duplicates": 0, "ohlc_violations": 0, "first_feature_date": None,
                    "feature_rows": 0, "first_model_eligible": None, "model_eligible_percentage": 0.0,
                    "valid_target_5d": 0, "valid_target_10d": 0, "valid_target_20d": 0,
                    "ingestion_seconds": state["ingestion_seconds"],
                    "build_seconds": build_report.get("feature_build_seconds_by_ticker", {}).get(ticker),
                    "warnings": state["warnings"]}
        trading_dates = _dates(bars, "trading_date")
        first, last = min(trading_dates), max(trading_dates)
        expected = [day for day in self._requested_sessions if day >= first]
        present = set(trading_dates)
        missing = [day for day in expected if day not in present]
        now = datetime.now(timezone.utc)
        pending = [day for day in expected if self.builder.decision_time(day).astimezone(timezone.utc) > now]
        unexpected = [day for day in missing if day not in pending]
        availability = pd.to_datetime(bars["available_at"], utc=True, errors="coerce")
        unavailable_bars = int((availability.isna() | (availability > now)).sum())
        if unexpected:
            state["warnings"].append(f"{len(unexpected)} unexpected missing sessions")
        duplicate_count = int(bars.duplicated(["ticker", "trading_date", "provider"]).sum())
        ohlc_bad = ((bars["high"] < bars[["open", "low", "close"]].max(axis=1)) |
                    (bars["low"] > bars[["open", "high", "close"]].min(axis=1)))
        action_types = actions["action_type"].astype(str).str.lower() if not actions.empty else pd.Series(dtype=str)
        split_mask, dividend_mask = action_types.str.endswith("split"), action_types.str.endswith("dividend")
        eligible = group[group["model_eligible"]] if not group.empty else group
        return {
            "status": state["status"], "error": state["error"], "first_raw_date": first, "last_raw_date": last,
            "raw_bars": int(len(bars)), "expected_sessions_from_first_raw": len(expected),
            "unexpected_missing_sessions": unexpected, "pending_sessions_before_cutoff": pending,
            "raw_bars_not_yet_available": unavailable_bars,
            "split_count": int(split_mask.sum()),
            "split_dates": list(_dates(actions[split_mask], "effective_date")) if split_mask.any() else [],
            "dividend_count": int(dividend_mask.sum()),
            "dividend_date_examples": list(_dates(actions[dividend_mask].head(5), "effective_date")) if dividend_mask.any() else [],
            "duplicates": duplicate_count, "ohlc_violations": int(ohlc_bad.sum()),
            "first_feature_date": min(_dates(group, "decision_date")) if not group.empty else None,
            "feature_rows": int(len(group)),
            "first_model_eligible": min(_dates(eligible, "decision_date")) if not eligible.empty else None,
            "model_eligible_percentage": float(group["model_eligible"].mean() * 100) if not group.empty else 0.0,
            "valid_target_5d": int(target_group.get("target_return_5d", pd.Series(dtype=float)).notna().sum()),
            "valid_target_10d": int(target_group.get("target_return_10d", pd.Series(dtype=float)).notna().sum()),
            "valid_target_20d": int(target_group.get("target_return_20d", pd.Series(dtype=float)).notna().sum()),
            "ingestion_seconds": state["ingestion_seconds"],
            "build_seconds": build_report.get("feature_build_seconds_by_ticker", {}).get(ticker),
            "warnings": state["warnings"],
        }

    @staticmethod
    def _stats(values: pd.Series) -> dict[str, float | int | None]:
        if values.empty:
            return {"min": None, "median": None, "mean": None, "max": None}
        return {"min": int(values.min()), "median": float(values.median()),
                "mean": float(values.mean()), "max": int(values.max())}

    def _cross_sectional(self, features: pd.DataFrame, targets: pd.DataFrame | None) -> dict[str, Any]:
        if features.empty:
            return {}
        dates = sorted(set(_dates(features, "decision_date")))
        feature_counts = features.groupby("decision_date")["ticker"].nunique().reindex(dates, fill_value=0)
        eligible_counts = features[features["model_eligible"]].groupby("decision_date")["ticker"].nunique().reindex(dates, fill_value=0)
        if targets is None or targets.empty:
            target_counts = rank_counts = pd.Series(0, index=dates)
        else:
            target_counts = targets[targets["target_return_10d"].notna()].groupby("decision_date")["ticker"].nunique().reindex(dates, fill_value=0)
            rank_counts = targets[targets["target_rank_10d"].notna()].groupby("decision_date")["ticker"].nunique().reindex(dates, fill_value=0)
        return {"dates": len(dates), "assets_with_features": self._stats(feature_counts),
                "model_eligible": self._stats(eligible_counts),
                "target_return_10d": self._stats(target_counts),
                "target_rank_10d": self._stats(rank_counts)}

    def _ranking_diagnostics(self, targets: pd.DataFrame | None) -> dict[str, Any] | None:
        if targets is None or targets.empty:
            return None
        values = targets["target_rank_10d"].dropna()
        if not values.empty and not values.between(0, 1).all():
            raise ValueError("target_rank_10d is outside [0, 1]")
        counts = targets[targets["target_rank_10d"].notna()].groupby("decision_date")["ticker"].nunique()
        valid_returns = targets[targets["target_return_10d"].notna()].groupby("decision_date")["ticker"].nunique()
        all_dates = sorted(set(_dates(targets, "decision_date")))
        missing = []
        for day in all_dates:
            ranked = int(counts.get(day, 0))
            if ranked:
                continue
            available = int(valid_returns.get(day, 0))
            reason = "insufficient_valid_target_return_10d" if available < self.builder.minimum_rank_assets else "ranking_unavailable"
            missing.append({"decision_date": day, "valid_target_return_10d_assets": available, "reason": reason})
        return {"valid_rank_rows": int(values.count()), "rank_min": float(values.min()) if not values.empty else None,
                "rank_max": float(values.max()) if not values.empty else None,
                "dates_with_valid_ranking": int(len(counts)),
                "percentage_dates_with_valid_ranking": float(len(counts) / len(all_dates) * 100) if all_dates else 0.0,
                "average_ranked_assets_per_valid_date": float(counts.mean()) if not counts.empty else 0.0,
                "minimum_ranked_assets_per_valid_date": int(counts.min()) if not counts.empty else 0,
                "maximum_ranked_assets_per_valid_date": int(counts.max()) if not counts.empty else 0,
                "dates_without_ranking": missing}

    @staticmethod
    def _unexpected_nans(features: pd.DataFrame) -> dict[str, dict[str, float | int]]:
        if features.empty:
            return {}
        eligible = features[features["model_eligible"]]
        result = {}
        for column in QUANTITATIVE_FEATURE_COLUMNS:
            if column in DELIBERATE_NULL_FEATURES or column not in eligible:
                continue
            count = int(eligible[column].isna().sum())
            if count:
                result[column] = {"count": count, "percentage": float(count / len(eligible) * 100)}
        return result

    @staticmethod
    def _records(frame: pd.DataFrame, column: str, *, ascending: bool, limit: int = 25) -> list[dict[str, Any]]:
        subset = frame[["ticker", "decision_date", column]].dropna().sort_values(column, ascending=ascending).head(limit)
        return subset.to_dict("records")

    def _outliers_and_extremes(self, features: pd.DataFrame) -> tuple[dict[str, Any], dict[str, Any]]:
        rules = {"abs_return_1d_gt_0_30": ("return_1d", lambda s: s.abs() > .30),
                 "abs_return_5d_gt_0_60": ("return_5d", lambda s: s.abs() > .60),
                 "volatility_20d_gt_1_50": ("volatility_20d", lambda s: s > 1.50),
                 "volume_ratio_20d_gt_10": ("volume_ratio_20d", lambda s: s > 10),
                 "atr_pct_gt_0_25": ("atr_pct", lambda s: s > .25)}
        outliers = {"thresholds_are_diagnostic_only": True}
        for name, (column, predicate) in rules.items():
            flagged = features[predicate(features[column].fillna(0))]
            outliers[name] = {"count": int(len(flagged)),
                              "observations": flagged[["ticker", "decision_date", column]].head(100).to_dict("records"),
                              "observations_truncated": len(flagged) > 100}
        extremes = {
            "largest_return_1d": self._records(features, "return_1d", ascending=False),
            "smallest_return_1d": self._records(features, "return_1d", ascending=True),
            "largest_return_10d": self._records(features, "return_10d", ascending=False),
            "largest_volatility_20d": self._records(features, "volatility_20d", ascending=False),
            "largest_volume_ratio_20d": self._records(features, "volume_ratio_20d", ascending=False),
            "largest_atr_pct": self._records(features, "atr_pct", ascending=False),
        }
        return outliers, extremes

    def _split_validation(self, tickers: list[str]) -> dict[str, Any]:
        events = []
        for ticker in tickers:
            raw, actions = self.market_store.read_bars(ticker), self.market_store.read_actions(ticker)
            if raw.empty or actions.empty:
                continue
            split_mask = actions["action_type"].astype(str).str.lower().str.endswith("split")
            for action in actions[split_mask].itertuples(index=False):
                split_day = pd.Timestamp(action.effective_date).date()
                days, cursor = [split_day], split_day
                for _ in range(3):
                    cursor = self.calendar.previous_session(cursor); days.insert(0, cursor)
                cursor = split_day
                for _ in range(3):
                    cursor = self.calendar.next_session(cursor); days.append(cursor)
                as_of_day = days[-1]
                view = build_split_adjusted_series_as_of(
                    raw, actions, decision_date=as_of_day, decision_time=self.builder.decision_time(as_of_day),
                )
                indexed = view.set_index("trading_date") if not view.empty else pd.DataFrame()
                returns = indexed["split_adjusted_close"].pct_change() if not view.empty else pd.Series(dtype=float)
                event_return = returns.get(split_day, np.nan)
                window_returns = returns.reindex(days)
                passed = bool(window_returns.notna().iloc[1:].all() and pd.notna(event_return) and abs(event_return) <= .30)
                events.append({"ticker": ticker, "split_date": split_day, "split_factor": float(action.split_factor),
                               "adjusted_return_1d_on_split": event_return, "maximum_absolute_return_1d_in_window": window_returns.abs().max(),
                               "validation_passed": passed})
        return {"events": events, "total": len(events),
                "passed": sum(item["validation_passed"] for item in events),
                "failed": [item for item in events if not item["validation_passed"]]}

    def _dataset_sizes(self) -> dict[str, int]:
        def total(root: Path) -> int:
            return sum(path.stat().st_size for path in root.rglob("*") if path.is_file()) if root.exists() else 0
        return {"raw": total(self.market_store.raw_daily.parent.parent),
                "processed": total(self.market_store.latest_basis_split_adjusted.parent.parent),
                "features": total(self.feature_store.features), "targets": total(self.feature_store.targets)}
