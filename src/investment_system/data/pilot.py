"""Diagnostics and orchestration for the small Phase 1C real-data pilot."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

import numpy as np
import pandas as pd

from investment_system.data.calendar import TradingCalendar
from investment_system.data.ingestion import MarketDataIngestionService
from investment_system.data.normalization import AS_OF_VERSION, build_split_adjusted_series_as_of
from investment_system.data.schemas.features import QUANTITATIVE_FEATURE_COLUMNS
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.features.store_builder import QuantitativeFeatureStoreBuilder


@dataclass(frozen=True)
class PilotRequest:
    raw_start: date
    feature_start: date
    end: date
    tickers: tuple[str, ...]
    benchmark: str
    with_targets: bool = False

    @property
    def all_tickers(self) -> tuple[str, ...]:
        return tuple(dict.fromkeys((self.benchmark, *self.tickers)))


def _dates(frame: pd.DataFrame, column: str) -> pd.Series:
    return pd.to_datetime(frame[column]).dt.date


def _json_value(value: Any) -> Any:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, (date, pd.Timestamp)):
        return str(value)
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


class RealDataPilot:
    """Run ingestion, feature construction, and evidence-rich diagnostics."""

    def __init__(
        self,
        market_store: MarketDataStore,
        feature_store: QuantitativeFeatureStore,
        calendar: TradingCalendar,
        builder: QuantitativeFeatureStoreBuilder,
        report_path: str | Path,
        ingestion: MarketDataIngestionService | None = None,
    ) -> None:
        self.market_store = market_store
        self.feature_store = feature_store
        self.calendar = calendar
        self.builder = builder
        self.report_path = Path(report_path)
        self.ingestion = ingestion

    def run(self, request: PilotRequest, *, skip_download: bool = False, skip_features: bool = False) -> dict[str, Any]:
        if request.raw_start > request.feature_start or request.feature_start > request.end:
            raise ValueError("expected raw_start <= feature_start <= end")
        started = perf_counter()
        previous: dict[str, Any] = {}
        if self.report_path.exists():
            try:
                previous = json.loads(self.report_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                previous = {}
        ingestion_seconds: dict[str, float] = {}
        ingestion_summaries: dict[str, Any] = {}
        if not skip_download:
            if self.ingestion is None:
                raise ValueError("ingestion service is required unless --skip-download is used")
            for ticker in request.all_tickers:
                step = perf_counter()
                summary = self.ingestion.ingest_ticker(ticker, request.raw_start, request.end)
                ingestion_seconds[ticker] = perf_counter() - step
                ingestion_summaries[ticker] = asdict(summary)

        raw = {ticker: self._raw_diagnostics(ticker, request.raw_start, request.end) for ticker in request.all_tickers}
        empty = [ticker for ticker, diagnostic in raw.items() if diagnostic["bars"] == 0]
        if empty:
            raise ValueError(f"raw data is missing for: {', '.join(empty)}")

        build_report: dict[str, Any] = {}
        if not skip_features:
            built = self.builder.build(
                list(request.all_tickers), request.feature_start, request.end,
                with_targets=request.with_targets,
            )
            features, targets, build_report = built.features, built.targets, built.report
        else:
            features = self._range(self.feature_store.read_features(), request, "decision_date")
            targets = self._range(self.feature_store.read_targets(), request, "decision_date") if request.with_targets else None

        feature_diagnostics = {
            ticker: self._feature_diagnostics(features, ticker, targets) for ticker in request.all_tickers
        }
        pit = self._point_in_time_checks(features, request)
        if not pit["passed"]:
            raise ValueError("point-in-time validation failed; report was not accepted")
        split_windows = {
            ticker: self._split_windows(ticker) for ticker in request.all_tickers
        }
        benchmark_nan = self._benchmark_nan_diagnostics(features, request.benchmark)
        outliers = self._outliers(features)
        target_diagnostics = self._target_diagnostics(features, targets, split_windows) if request.with_targets else None
        sizes = self._sizes(request)
        report = {
            "phase": "1C-real-data-pilot",
            "status": "passed",
            "request": asdict(request),
            "ingestion": ingestion_summaries or previous.get("ingestion", {}),
            "raw_by_ticker": raw,
            "features_by_ticker": feature_diagnostics,
            "split_windows": split_windows,
            "point_in_time": pit,
            "benchmark_feature_nans": benchmark_nan,
            "outliers_diagnostic_only": outliers,
            "targets": target_diagnostics,
            "performance": {
                "ingestion_seconds_by_ticker": ingestion_seconds or previous.get("performance", {}).get("ingestion_seconds_by_ticker", {}),
                "feature_build_seconds_by_ticker": build_report.get("feature_build_seconds_by_ticker", {}) or previous.get("performance", {}).get("feature_build_seconds_by_ticker", {}),
                "total_seconds": perf_counter() - started,
                "stages_skipped": {"download": skip_download, "features": skip_features},
                "file_sizes_bytes": sizes,
            },
            "global_summary": {
                "tickers": len(request.all_tickers),
                "raw_bars": sum(item["bars"] for item in raw.values()),
                "feature_rows": int(len(features)),
                "model_eligible_rows": int(features["model_eligible"].sum()) if not features.empty else 0,
                "raw_duplicates": sum(item["duplicates"] for item in raw.values()),
                "ohlc_violations": sum(item["ohlc_violations"] for item in raw.values()),
                "unexpected_raw_gaps": sum(len(item["unexpected_missing_sessions"]) for item in raw.values()),
                "unexpected_benchmark_nans": benchmark_nan["unexpected_columns"],
                "pit_passed": pit["passed"],
            },
        }
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.report_path.with_suffix(".tmp.json")
        temporary.write_text(json.dumps(report, indent=2, default=_json_value), encoding="utf-8")
        temporary.replace(self.report_path)
        return report

    def _range(self, frame: pd.DataFrame, request: PilotRequest, column: str) -> pd.DataFrame:
        if frame.empty:
            return frame
        values = _dates(frame, column)
        return frame[frame["ticker"].isin(request.all_tickers) & (values >= request.feature_start) & (values <= request.end)].copy()

    def _sessions(self, start: date, end: date) -> list[date]:
        return [date.fromordinal(value) for value in range(start.toordinal(), end.toordinal() + 1)
                if self.calendar.is_session(date.fromordinal(value))]

    def _raw_diagnostics(self, ticker: str, requested_start: date, requested_end: date) -> dict[str, Any]:
        bars = self.market_store.read_bars(ticker)
        actions = self.market_store.read_actions(ticker)
        if bars.empty:
            return {"first_date": None, "last_date": None, "bars": 0, "expected_sessions": 0,
                    "missing_sessions": [], "pending_sessions_before_decision_cutoff": [],
                    "unexpected_missing_sessions": [], "split_count": 0, "split_dates": [], "dividend_count": 0,
                    "dividend_dates": [], "duplicates": 0, "ohlc_violations": 0,
                    "price_min": None, "price_max": None, "volume_min": None, "volume_max": None}
        trading_dates = _dates(bars, "trading_date")
        first, last = trading_dates.min(), trading_dates.max()
        expected = self._sessions(requested_start, requested_end)
        present = set(trading_dates)
        missing = [value for value in expected if value not in present]
        now = datetime.now(timezone.utc)
        pending = [value for value in missing if self.builder.decision_time(value).astimezone(timezone.utc) > now]
        duplicate_count = int(bars.duplicated(["ticker", "trading_date", "provider"]).sum())
        ohlc_bad = ((bars["high"] < bars[["open", "low", "close"]].max(axis=1)) |
                    (bars["low"] > bars[["open", "high", "close"]].min(axis=1)))
        action_types = actions["action_type"].astype(str).str.lower() if not actions.empty else pd.Series(dtype=str)
        split_mask = action_types.str.endswith("split")
        dividend_mask = action_types.str.endswith("dividend")
        return {
            "first_date": first, "last_date": last, "bars": int(len(bars)),
            "expected_sessions": len(expected),
            "missing_sessions": missing,
            "pending_sessions_before_decision_cutoff": pending,
            "unexpected_missing_sessions": [value for value in missing if value not in pending],
            "split_count": int(split_mask.sum()),
            "split_dates": list(_dates(actions[split_mask], "effective_date")) if split_mask.any() else [],
            "dividend_count": int(dividend_mask.sum()),
            "dividend_dates": list(_dates(actions[dividend_mask], "effective_date")) if dividend_mask.any() else [],
            "duplicates": duplicate_count, "ohlc_violations": int(ohlc_bad.sum()),
            "price_min": float(bars[["open", "high", "low", "close"]].min().min()),
            "price_max": float(bars[["open", "high", "low", "close"]].max().max()),
            "volume_min": float(bars["volume"].min()), "volume_max": float(bars["volume"].max()),
        }

    def _feature_diagnostics(self, features: pd.DataFrame, ticker: str, targets: pd.DataFrame | None) -> dict[str, Any]:
        group = features[features["ticker"] == ticker] if not features.empty else features
        target_group = targets[targets["ticker"] == ticker] if targets is not None and not targets.empty else pd.DataFrame()
        valid_targets = {str(horizon): int(target_group[f"target_return_{horizon}d"].notna().sum())
                         for horizon in (5, 10, 20)} if not target_group.empty else {str(horizon): 0 for horizon in (5, 10, 20)}
        if group.empty:
            return {"features_built": 0, "first_model_eligible": None, "model_eligible_percentage": 0.0,
                    "nan_percentage_by_feature": {}, "infinities": 0, "valid_targets": valid_targets}
        eligible = group[group["model_eligible"]]
        numeric = group.select_dtypes(include=[np.number])
        return {
            "features_built": int(len(group)),
            "first_model_eligible": _dates(eligible, "decision_date").min() if not eligible.empty else None,
            "model_eligible_percentage": float(group["model_eligible"].mean() * 100),
            "nan_percentage_by_feature": {name: float(group[name].isna().mean() * 100)
                                           for name in QUANTITATIVE_FEATURE_COLUMNS if name in group},
            "infinities": int(np.isinf(numeric.to_numpy()).sum()),
            "valid_targets": valid_targets,
        }

    def _point_in_time_checks(self, features: pd.DataFrame, request: PilotRequest) -> dict[str, Any]:
        checks: list[dict[str, Any]] = []
        for ticker in request.all_tickers:
            group = features[features["ticker"] == ticker].sort_values("decision_date") if not features.empty else features
            if group.empty:
                checks.append({"ticker": ticker, "passed": False, "reason": "no feature rows"})
                continue
            raw, actions = self.market_store.read_bars(ticker), self.market_store.read_actions(ticker)
            indices = {0, len(group) // 2, len(group) - 1}
            if not actions.empty:
                split_dates = set(_dates(actions[actions["action_type"].astype(str).str.lower().str.endswith("split")], "effective_date"))
                group_dates = list(_dates(group, "decision_date"))
                for split_day in split_dates:
                    prior = [index for index, day in enumerate(group_dates) if day < split_day]
                    if prior:
                        indices.add(prior[-1])
            indices = sorted(indices)
            for index in indices:
                row = group.iloc[index]
                decision_day = pd.Timestamp(row["decision_date"]).date()
                decision_time = pd.Timestamp(row["decision_time"])
                view = build_split_adjusted_series_as_of(raw, actions, decision_date=decision_day, decision_time=decision_time.to_pydatetime())
                dates_ok = not view.empty and max(_dates(view, "trading_date")) <= decision_day
                availability = pd.to_datetime(raw[raw["trading_date"].isin(view["trading_date"])] ["available_at"], utc=True, errors="coerce") if not view.empty else pd.Series(dtype="datetime64[ns, UTC]")
                availability_ok = bool(availability.notna().all() and (availability <= decision_time.tz_convert("UTC")).all())
                time_ok = decision_time.tz_convert(self.builder.timezone).strftime("%H:%M") == "20:15"
                view_row = view[_dates(view, "trading_date") == decision_day]
                basis_ok = (not view_row.empty
                            and view["normalization_basis"].eq("as_of").all()
                            and view["normalization_version"].eq(AS_OF_VERSION).all()
                            and np.isclose(float(row["split_adjusted_close"]), float(view_row.iloc[-1]["split_adjusted_close"])))
                checks.append({"ticker": ticker, "decision_date": decision_day, "decision_time": decision_time,
                               "normalization_version": AS_OF_VERSION, "as_of_input_matches_feature": basis_ok,
                               "latest_basis_used": False if basis_ok else None,
                               "no_future_dates": dates_ok, "availability_cutoff_respected": availability_ok,
                               "decision_time_20_15_new_york": time_ok,
                               "passed": dates_ok and availability_ok and time_ok and basis_ok})
        return {"passed": bool(checks) and all(item["passed"] for item in checks), "samples": checks}

    def _split_windows(self, ticker: str) -> list[dict[str, Any]]:
        raw, actions = self.market_store.read_bars(ticker), self.market_store.read_actions(ticker)
        if actions.empty:
            return []
        split_mask = actions["action_type"].astype(str).str.lower().str.endswith("split")
        windows: list[dict[str, Any]] = []
        for action in actions[split_mask].itertuples(index=False):
            split_day = pd.Timestamp(action.effective_date).date()
            before, cursor = [], split_day
            for _ in range(3):
                cursor = self.calendar.previous_session(cursor)
                before.append(cursor)
            after, cursor = [], split_day
            for _ in range(3):
                cursor = self.calendar.next_session(cursor)
                after.append(cursor)
            days = list(reversed(before)) + [split_day] + after
            as_of_day = days[-1]
            view = build_split_adjusted_series_as_of(raw, actions, decision_date=as_of_day,
                                                     decision_time=self.builder.decision_time(as_of_day))
            by_date = view.set_index("trading_date") if not view.empty else pd.DataFrame()
            adjusted_return = by_date["split_adjusted_close"].pct_change() if not view.empty else pd.Series(dtype=float)
            raw_by_date = raw.assign(trading_date=_dates(raw, "trading_date")).set_index("trading_date")
            rows = []
            for day in days:
                rows.append({"trading_date": day,
                             "raw_close": _json_value(raw_by_date.at[day, "close"]) if day in raw_by_date.index else None,
                             "split_adjusted_close": _json_value(by_date.at[day, "split_adjusted_close"]) if day in by_date.index else None,
                             "return_1d": _json_value(adjusted_return.get(day))})
            windows.append({"split_date": split_day, "split_factor": float(action.split_factor),
                            "as_of_date": as_of_day, "rows": rows})
        return windows

    @staticmethod
    def _benchmark_nan_diagnostics(features: pd.DataFrame, benchmark: str) -> dict[str, Any]:
        benchmark_columns = ["spy_return_1d", "spy_return_5d", "spy_return_20d", "excess_return_5d",
                             "excess_return_20d", "correlation_spy_20d", "correlation_spy_60d",
                             "beta_20d", "beta_60d"]
        eligible = features[features["model_eligible"]] if not features.empty else features
        percentages = {name: float(eligible[name].isna().mean() * 100) for name in benchmark_columns if name in eligible}
        return {"benchmark": benchmark, "eligible_rows": int(len(eligible)), "nan_percentage": percentages,
                "unexpected_columns": [name for name, percentage in percentages.items() if percentage > 0]}

    @staticmethod
    def _outliers(features: pd.DataFrame) -> dict[str, Any]:
        rules = {"abs_return_1d_gt_0_30": ("return_1d", lambda s: s.abs() > .30),
                 "abs_return_5d_gt_0_60": ("return_5d", lambda s: s.abs() > .60),
                 "volatility_20d_gt_1_50": ("volatility_20d", lambda s: s > 1.50),
                 "volume_ratio_20d_gt_10": ("volume_ratio_20d", lambda s: s > 10),
                 "atr_pct_gt_0_25": ("atr_pct", lambda s: s > .25)}
        result: dict[str, Any] = {"thresholds_are_diagnostic_only": True}
        for name, (column, predicate) in rules.items():
            flagged = features[predicate(features[column].fillna(0))] if column in features else features.iloc[0:0]
            result[name] = {"count": int(len(flagged)), "examples": flagged[["ticker", "decision_date", column]].head(20).to_dict("records") if not flagged.empty else []}
        return result

    @staticmethod
    def _target_diagnostics(features: pd.DataFrame, targets: pd.DataFrame | None, split_windows: dict[str, Any]) -> dict[str, Any]:
        if targets is None or targets.empty:
            return {"rows": 0, "error": "targets requested but unavailable"}
        keys = set(zip(features["ticker"], _dates(features, "decision_date")))
        target_keys = list(zip(targets["ticker"], _dates(targets, "decision_date")))
        horizons: dict[str, Any] = {}
        for horizon in (5, 10, 20):
            column = f"target_return_{horizon}d"
            valid = targets[column].dropna()
            trailing_ok = all(group.tail(horizon)[column].isna().all() for _, group in targets.sort_values("decision_date").groupby("ticker"))
            horizons[str(horizon)] = {"valid": int(valid.count()), "min": float(valid.min()) if not valid.empty else None,
                                      "max": float(valid.max()) if not valid.empty else None, "trailing_nan": trailing_ok}
        split_neighborhoods: set[tuple[str, date]] = set()
        for ticker, windows in split_windows.items():
            for window in windows:
                split_day = window["split_date"]
                for day in _dates(targets[targets["ticker"] == ticker], "decision_date"):
                    if abs((day - split_day).days) <= 35:
                        split_neighborhoods.add((ticker, day))
        split_rows = targets[[key in split_neighborhoods for key in target_keys]]
        ranges = {"5": 1.0, "10": 1.5, "20": 2.0}
        return {"rows": int(len(targets)), "horizons": horizons,
                "target_keys_without_features": sum(key not in keys for key in target_keys),
                "rank_all_nan_expected_small_universe": bool(targets["target_rank_10d"].isna().all()),
                "reasonable_range_diagnostic_thresholds_abs": ranges,
                "outside_reasonable_range": {horizon: int((targets[f"target_return_{horizon}d"].abs() > threshold).sum())
                                               for horizon, threshold in ranges.items()},
                "split_date_target_max_abs": {column: float(split_rows[column].abs().max()) if not split_rows.empty and split_rows[column].notna().any() else None
                                               for column in ("target_return_5d", "target_return_10d", "target_return_20d")}}

    def _sizes(self, request: PilotRequest) -> dict[str, Any]:
        raw = {ticker: {"bars": self.market_store.bar_path(ticker).stat().st_size if self.market_store.bar_path(ticker).exists() else 0,
                        "actions": self.market_store.action_path(ticker).stat().st_size if self.market_store.action_path(ticker).exists() else 0}
               for ticker in request.all_tickers}
        return {"raw_by_ticker": raw,
                "features": sum(path.stat().st_size for path in self.feature_store.features.glob("year=*/data.parquet")),
                "targets": sum(path.stat().st_size for path in self.feature_store.targets.glob("year=*/data.parquet"))}
