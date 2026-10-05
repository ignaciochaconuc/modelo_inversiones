from investment_system.data.schemas.base import PointInTimeRecord

class EarningsRecord(PointInTimeRecord):
    ticker: str
    fiscal_period: str
    eps_actual: float | None = None
    eps_consensus: float | None = None
    revenue_actual: float | None = None
    revenue_consensus: float | None = None
