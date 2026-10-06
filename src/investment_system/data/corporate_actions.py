"""Conservative detection and audit metadata for unmodelled corporate actions.

This module never changes raw prices. It classifies discontinuities and produces
exclusion metadata; economic adjustments beyond simple splits remain out of scope.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
from pathlib import Path
from typing import Any

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator

from investment_system.core.config import load_yaml
from investment_system.data.calendar import TradingCalendar
from investment_system.data.normalization import build_latest_basis_split_adjusted_series


EVENT_SCHEMA_VERSION = "1"


class CorporateActionEvent(BaseModel):
    """Normalized detected or manually reviewed corporate-action event."""

    model_config = ConfigDict(extra="forbid")
    event_id: str
    ticker: str
    event_date: date
    event_type: str
    source: str
    confidence: float = Field(ge=0, le=1)
    known_at: datetime
    detected_at: datetime
    adjustment_supported: bool = False
    training_exclusion: bool = False
    notes: str = ""
    schema_version: str = EVENT_SCHEMA_VERSION

    @field_validator("known_at", "detected_at")
    @classmethod
    def aware_timestamp(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("event timestamps must be timezone-aware")
        return value


def _event_id(ticker: str, event_date: date, event_type: str, source: str) -> str:
    value = f"{ticker}|{event_date.isoformat()}|{event_type}|{source}".encode()
    return hashlib.sha256(value).hexdigest()[:20]


def load_corporate_action_overrides(
    path: str | Path = "config/corporate_action_overrides.yaml",
) -> list[dict[str, Any]]:
    payload = load_yaml(path)
    events = payload.get("events", [])
    if not isinstance(events, list):
        raise ValueError("corporate action overrides events must be a list")
    return events


def detect_corporate_action_events(
    raw_bars: pd.DataFrame,
    actions: pd.DataFrame,
    *,
    ticker: str,
    overrides: list[dict[str, Any]] | None = None,
    return_threshold: float = 0.30,
    adjusted_continuity_threshold: float = 0.20,
    extraordinary_distribution_ratio: float = 0.10,
    detected_at: datetime | None = None,
) -> pd.DataFrame:
    """Detect extreme discontinuities and classify only when evidence is combined."""
    now = detected_at or datetime.now(timezone.utc)
    overrides = overrides or []
    records: list[CorporateActionEvent] = []
    if not raw_bars.empty:
        latest = build_latest_basis_split_adjusted_series(raw_bars, actions).sort_values("trading_date")
        audit_columns = [name for name in ("ticker", "trading_date", "provider", "available_at", "adjusted_close")
                         if name in raw_bars]
        latest = latest.merge(
            raw_bars[audit_columns], on=["ticker", "trading_date", "provider"], how="left",
            validate="one_to_one",
        )
        latest["internal_return_1d"] = latest["split_adjusted_close"].pct_change()
        if "adjusted_close" in latest:
            latest["provider_adjusted_return_1d"] = latest["adjusted_close"].pct_change(fill_method=None)
        else:
            latest["provider_adjusted_return_1d"] = float("nan")
        action_dates = pd.to_datetime(actions.get("effective_date", pd.Series(dtype=object))).dt.date
        for row in latest[latest["internal_return_1d"].abs() > return_threshold].itertuples(index=False):
            event_date = pd.Timestamp(row.trading_date).date()
            nearby = actions[action_dates == event_date] if not actions.empty else pd.DataFrame()
            types = nearby.get("action_type", pd.Series(dtype=str)).astype(str).str.lower()
            split = bool(types.str.endswith("split").any())
            dividends = pd.to_numeric(nearby.get("dividend_cash", pd.Series(dtype=float)), errors="coerce")
            prior_close = float(row.split_adjusted_close) / (1 + float(row.internal_return_1d))
            large_distribution = bool((dividends / prior_close >= extraordinary_distribution_ratio).fillna(False).any())
            provider_return = row.provider_adjusted_return_1d
            provider_continuity = bool(
                pd.notna(provider_return)
                and abs(float(provider_return)) <= adjusted_continuity_threshold
                and abs(float(row.internal_return_1d) - float(provider_return)) >= return_threshold
            )
            if split and (large_distribution or provider_continuity):
                event_type, confidence = "complex_recapitalization", 0.95
            elif large_distribution and provider_continuity:
                event_type, confidence = "complex_distribution", 0.95
            elif provider_continuity:
                event_type, confidence = "provider_adjustment_inconsistency", 0.80
            elif split:
                event_type, confidence = "split_adjustment_inconsistency", 0.70
            else:
                event_type, confidence = "unexplained_price_discontinuity", 0.40
            evidence = split or large_distribution or provider_continuity
            timestamps = pd.to_datetime(nearby.get("available_at", pd.Series(dtype=object)), utc=True, errors="coerce")
            bar_known = pd.to_datetime(getattr(row, "available_at"), utc=True).to_pydatetime()
            known_at = max([bar_known, *[value.to_pydatetime() for value in timestamps.dropna()]])
            notes = (
                f"split_only_return={float(row.internal_return_1d):.6f}; "
                f"provider_adjusted_return={float(provider_return):.6f}; " if pd.notna(provider_return) else
                f"split_only_return={float(row.internal_return_1d):.6f}; provider_adjusted_return=missing; "
            )
            notes += f"split={split}; extraordinary_distribution={large_distribution}"
            records.append(CorporateActionEvent(
                event_id=_event_id(ticker, event_date, event_type, "heuristic"), ticker=ticker,
                event_date=event_date, event_type=event_type, source="heuristic",
                confidence=confidence, known_at=known_at, detected_at=now,
                adjustment_supported=False, training_exclusion=evidence, notes=notes,
            ))
    for override in overrides:
        if str(override.get("ticker", "")).upper() != ticker.upper():
            continue
        event_date = date.fromisoformat(str(override["date"]))
        event_type = str(override.get("classification", "manual_review"))
        known_at_raw = override.get("known_at")
        known_at = pd.Timestamp(known_at_raw).to_pydatetime() if known_at_raw else now
        if known_at.tzinfo is None:
            known_at = known_at.replace(tzinfo=timezone.utc)
        records.append(CorporateActionEvent(
            event_id=_event_id(ticker, event_date, event_type, "manual_override"), ticker=ticker,
            event_date=event_date, event_type=event_type, source="manual_override",
            confidence=float(override.get("confidence", 1.0)), known_at=known_at,
            detected_at=now, adjustment_supported=False,
            training_exclusion=bool(override.get("training_exclusion", False)),
            notes=str(override.get("notes", "reviewed override")),
        ))
    columns = list(CorporateActionEvent.model_fields)
    if not records:
        return pd.DataFrame(columns=columns)
    frame = pd.DataFrame([item.model_dump(mode="python") for item in records])
    return frame.sort_values(["ticker", "event_date", "source"]).drop_duplicates("event_id", keep="last")


def event_window(calendar: TradingCalendar, event_date: date, before: int = 1, after: int = 1) -> set[date]:
    result = {event_date}
    cursor = event_date
    for _ in range(before):
        cursor = calendar.previous_session(cursor)
        result.add(cursor)
    cursor = event_date
    for _ in range(after):
        cursor = calendar.next_session(cursor)
        result.add(cursor)
    return result


def add_feature_contamination_flags(
    features: pd.DataFrame,
    events: pd.DataFrame,
    calendar: TradingCalendar,
    *,
    before: int = 1,
    after: int = 1,
) -> pd.DataFrame:
    """Add point-in-time-safe flags; future-known events never mark earlier features."""
    result = features.copy()
    result["feature_corporate_action_contaminated"] = False
    result["corporate_action_reason"] = None
    result["corporate_action_event_id"] = None
    if result.empty or events.empty:
        return result
    for event in events[events["training_exclusion"].fillna(False)].itertuples(index=False):
        window = event_window(calendar, pd.Timestamp(event.event_date).date(), before, after)
        known_at = pd.to_datetime(event.known_at, utc=True)
        decisions = pd.to_datetime(result["decision_time"], utc=True)
        dates = pd.to_datetime(result["decision_date"]).dt.date
        mask = (result["ticker"] == event.ticker) & dates.isin(window) & (decisions >= known_at)
        result.loc[mask, "feature_corporate_action_contaminated"] = True
        result.loc[mask, "corporate_action_reason"] = event.event_type
        result.loc[mask, "corporate_action_event_id"] = event.event_id
    return result

