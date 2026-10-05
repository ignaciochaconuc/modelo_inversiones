from datetime import date
from investment_system.data.calendar import XNYSTradingCalendar

def test_xnys_calendar_handles_holiday_and_sessions() -> None:
    calendar = XNYSTradingCalendar()
    assert not calendar.is_session(date(2025, 12, 25))
    assert calendar.next_session(date(2025, 12, 25)) == date(2025, 12, 26)
    assert calendar.previous_session(date(2025, 12, 25)) == date(2025, 12, 24)
    assert calendar.session_open(date(2025, 12, 24)).tzinfo is not None
