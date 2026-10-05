from datetime import date, datetime
from typing import Protocol

import exchange_calendars as xcals

class TradingCalendar(Protocol):
    def is_session(self, value: date) -> bool: ...
    def previous_session(self, value: date) -> date: ...
    def next_session(self, value: date) -> date: ...
    def session_open(self, value: date) -> datetime: ...
    def session_close(self, value: date) -> datetime: ...

class XNYSTradingCalendar:
    """NYSE calendar backed by exchange-calendars; returned times are UTC-aware."""
    def __init__(self) -> None:
        self._calendar = xcals.get_calendar("XNYS")

    def is_session(self, value: date) -> bool:
        return bool(self._calendar.is_session(value.isoformat()))

    def previous_session(self, value: date) -> date:
        session = self._calendar.date_to_session(value.isoformat(), direction="previous")
        if session.date() == value:
            session = self._calendar.previous_session(session)
        return session.date()

    def next_session(self, value: date) -> date:
        session = self._calendar.date_to_session(value.isoformat(), direction="next")
        if session.date() == value:
            session = self._calendar.next_session(session)
        return session.date()

    def session_open(self, value: date) -> datetime:
        return self._calendar.session_open(value.isoformat()).to_pydatetime()

    def session_close(self, value: date) -> datetime:
        return self._calendar.session_close(value.isoformat()).to_pydatetime()
