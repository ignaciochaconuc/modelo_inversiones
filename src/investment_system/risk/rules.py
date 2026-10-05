from pydantic import BaseModel, Field

class RiskLimits(BaseModel):
    max_position_weight: float = Field(default=0.10, gt=0, le=1)
    max_positions: int = Field(default=15, gt=0)
    max_portfolio_exposure: float = Field(default=1.0, gt=0)
    max_drawdown: float = Field(default=0.15, gt=0, le=1)
    max_daily_loss: float = Field(default=0.03, gt=0, le=1)
    max_asset_volatility: float | None = None
    max_event_risk: float = Field(default=0.8, ge=0, le=1)
    long_only: bool = True
    leverage_allowed: bool = False
    minimum_cash_weight: float = Field(default=0.0, ge=0, le=1)
