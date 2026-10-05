from pydantic import Field
from investment_system.data.schemas.base import PointInTimeRecord

class MarketBar(PointInTimeRecord):
    ticker: str = Field(min_length=1)
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    adjusted_close: float = Field(gt=0)
    volume: float = Field(ge=0)
