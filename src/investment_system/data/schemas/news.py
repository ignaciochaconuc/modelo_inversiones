from investment_system.data.schemas.base import PointInTimeRecord

class NewsRecord(PointInTimeRecord):
    source_id: str
    ticker: str | None = None
    headline: str
    url: str | None = None
    content: str | None = None
