from investment_system.data.schemas.base import PointInTimeRecord

class MacroRecord(PointInTimeRecord):
    series: str
    value: float
    unit: str | None = None
