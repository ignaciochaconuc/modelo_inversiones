"""Small contracts and shared causal scheduling for baseline allocations."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import Protocol
from zoneinfo import ZoneInfo

import pandas as pd

from investment_system.backtesting.schemas import TargetAllocation
from investment_system.data.calendar import TradingCalendar


@dataclass(frozen=True)
class StrategyPlan:
    """Deterministic allocations plus compact eligibility audit metadata."""

    strategy_name: str
    strategy_version: str
    allocations: Mapping[date, TargetAllocation]
    eligible_assets_by_date: Mapping[date, int] = field(default_factory=dict)

    def eligibility_summary(self) -> dict[str, float | int | None]:
        counts = list(self.eligible_assets_by_date.values())
        return {
            "decision_dates": len(self.allocations),
            "eligibility_observations": len(counts),
            "minimum_eligible_assets": min(counts) if counts else None,
            "maximum_eligible_assets": max(counts) if counts else None,
            "average_eligible_assets": (
                sum(counts) / len(counts) if counts else None
            ),
        }


class BaselineStrategy(Protocol):
    """A strategy only generates dated target allocations; it never simulates."""

    strategy_name: str
    strategy_version: str

    def generate_allocations(self, start: date, end: date) -> StrategyPlan: ...


def decision_time(
    session: date,
    *,
    timezone_name: str = "America/New_York",
    cutoff: str = "20:15",
) -> datetime:
    return datetime.combine(session, time.fromisoformat(cutoff), ZoneInfo(timezone_name))


def sessions(start: date, end: date, calendar: TradingCalendar) -> list[date]:
    if start > end:
        raise ValueError("start must be <= end")
    return [
        date.fromordinal(ordinal)
        for ordinal in range(start.toordinal(), end.toordinal() + 1)
        if calendar.is_session(date.fromordinal(ordinal))
    ]


def buy_and_hold_allocations(
    *,
    ticker: str,
    start: date,
    end: date,
    calendar: TradingCalendar,
    actions: pd.DataFrame,
    timezone_name: str = "America/New_York",
    cutoff: str = "20:15",
) -> dict[date, TargetAllocation]:
    """Initial full investment plus causal reinvestment decisions on ex-dates."""
    trading_sessions = sessions(start, end, calendar)
    if not trading_sessions:
        raise ValueError("strategy range contains no trading sessions")
    decision_dates = {trading_sessions[0]}
    if not actions.empty:
        required = {"action_type", "effective_date"}
        missing = required - set(actions)
        if missing:
            raise ValueError(f"corporate actions missing columns: {sorted(missing)}")
        action_types = actions["action_type"].astype(str).str.lower()
        dividend_dates = pd.to_datetime(
            actions.loc[action_types.str.endswith("dividend"), "effective_date"],
        )
        decision_dates.update(
            timestamp.date()
            for timestamp in dividend_dates
            if start <= timestamp.date() <= end
            and calendar.is_session(timestamp.date())
        )
    return {
        session: TargetAllocation(
            generated_at=decision_time(
                session, timezone_name=timezone_name, cutoff=cutoff,
            ),
            weights={ticker: 1.0},
            cash_weight=0.0,
        )
        for session in sorted(decision_dates)
    }
