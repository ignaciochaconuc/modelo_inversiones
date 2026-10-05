from datetime import datetime, timedelta, timezone
import pytest
from investment_system.core.exceptions import PointInTimeViolation
from investment_system.core.time_utils import validate_available_at

def test_rejects_information_available_after_decision() -> None:
    decision = datetime(2025, 1, 1, 21, tzinfo=timezone.utc)
    with pytest.raises(PointInTimeViolation):
        validate_available_at(decision + timedelta(seconds=1), decision)

def test_accepts_information_available_at_decision() -> None:
    decision = datetime(2025, 1, 1, 21, tzinfo=timezone.utc)
    validate_available_at(decision, decision)
