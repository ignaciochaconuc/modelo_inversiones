from collections.abc import Iterable
from datetime import date

from investment_system.core.exceptions import DataQualityError
from investment_system.data.calendar import TradingCalendar
from investment_system.data.schemas.market import MarketBar

def validate_market_bars(bars: Iterable[MarketBar]) -> list[MarketBar]:
    validated = list(bars)
    keys: set[tuple[str, date, str]] = set()
    for bar in validated:
        key = (bar.ticker, bar.trading_date, bar.provider)
        if key in keys:
            raise DataQualityError(f"duplicate market bar: {key}")
        keys.add(key)
    return validated

def unexpected_session_gaps(
    bars: Iterable[MarketBar], start_date: date, end_date: date, calendar: TradingCalendar
) -> list[date]:
    """Report missing exchange sessions without treating weekends/holidays as gaps."""
    present = {bar.trading_date for bar in bars}
    gaps: list[date] = []
    cursor = start_date
    while cursor <= end_date:
        if calendar.is_session(cursor) and cursor not in present:
            gaps.append(cursor)
        cursor = date.fromordinal(cursor.toordinal() + 1)
    return gaps
