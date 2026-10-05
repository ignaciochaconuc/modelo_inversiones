from datetime import datetime
from pydantic import BaseModel, Field

class Position(BaseModel):
    ticker: str
    weight: float = Field(ge=0, le=1)
    market_value: float = Field(ge=0)

class PortfolioState(BaseModel):
    as_of: datetime
    positions: list[Position] = Field(default_factory=list)
    cash_weight: float = Field(ge=0, le=1)

class AssetForecast(BaseModel):
    ticker: str
    expected_return: float
    risk: float = Field(ge=0)

class AllocationProposal(BaseModel):
    generated_at: datetime
    weights: dict[str, float]
    cash_weight: float
    objective_value: float | None = None
