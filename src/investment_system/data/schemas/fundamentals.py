from typing import Any
from investment_system.data.schemas.base import PointInTimeRecord

class FundamentalRecord(PointInTimeRecord):
    ticker: str
    period: str
    values: dict[str, float | None]
    filing_metadata: dict[str, Any] = {}
