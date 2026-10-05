from datetime import datetime
from investment_system.data.schemas.base import PointInTimeRecord

class EventRecord(PointInTimeRecord):
    event_id: str
    event_type: str
    scheduled_at: datetime
    ticker: str | None = None
    description: str | None = None
