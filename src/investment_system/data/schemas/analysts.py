from investment_system.data.schemas.base import PointInTimeRecord

class AnalystRecord(PointInTimeRecord):
    ticker: str
    firm: str | None = None
    rating: str | None = None
    target_price: float | None = None
    eps_estimate: float | None = None
    revenue_estimate: float | None = None
