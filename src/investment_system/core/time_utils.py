from datetime import date, datetime, time
from zoneinfo import ZoneInfo
from investment_system.core.exceptions import PointInTimeViolation

def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        raise ValueError("datetime must be timezone-aware")
    return value.astimezone(ZoneInfo("UTC"))

def validate_available_at(available_at: datetime | None, decision_time: datetime) -> None:
    if available_at is not None and ensure_utc(available_at) > ensure_utc(decision_time):
        raise PointInTimeViolation(f"information available at {available_at.isoformat()} after decision time {decision_time.isoformat()}")

def decision_time_for_date(decision_date: date, market_timezone: str = "America/New_York", hour: int = 16, minute: int = 15) -> datetime:
    return datetime.combine(decision_date, time(hour, minute), ZoneInfo(market_timezone))
