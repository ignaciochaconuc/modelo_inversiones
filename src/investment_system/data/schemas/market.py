from datetime import date
from enum import StrEnum
from pydantic import Field, model_validator
from investment_system.data.schemas.base import PointInTimeRecord

class MarketBar(PointInTimeRecord):
    ticker: str = Field(min_length=1, pattern=r"^[A-Z0-9.-]+$")
    trading_date: date
    provider: str = Field(min_length=1)
    schema_version: str = "1"
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: float = Field(ge=0)
    adjusted_open: float | None = Field(default=None, gt=0)
    adjusted_high: float | None = Field(default=None, gt=0)
    adjusted_low: float | None = Field(default=None, gt=0)
    adjusted_close: float | None = Field(default=None, gt=0)
    adjusted_volume: float | None = Field(default=None, ge=0)
    split_factor: float = Field(default=1.0, gt=0)
    dividend_cash: float = Field(default=0.0, ge=0)

    @model_validator(mode="after")
    def validate_ohlc(self) -> "MarketBar":
        if self.high < max(self.open, self.low, self.close):
            raise ValueError("high must be >= open, low, and close")
        if self.low > min(self.open, self.high, self.close):
            raise ValueError("low must be <= open, high, and close")
        if self.available_at and self.observed_at and self.available_at < self.observed_at:
            raise ValueError("available_at cannot precede observed_at for an EOD bar")
        return self

class CorporateActionType(StrEnum):
    SPLIT = "split"
    DIVIDEND = "dividend"

class CorporateAction(PointInTimeRecord):
    ticker: str = Field(min_length=1, pattern=r"^[A-Z0-9.-]+$")
    effective_date: date
    action_type: CorporateActionType
    provider: str = Field(min_length=1)
    schema_version: str = "1"
    split_factor: float | None = Field(default=None, gt=0)
    dividend_cash: float | None = Field(default=None, ge=0)
    currency: str | None = None

    @model_validator(mode="after")
    def validate_action_value(self) -> "CorporateAction":
        if self.action_type == CorporateActionType.SPLIT and self.split_factor is None:
            raise ValueError("split action requires split_factor")
        if self.action_type == CorporateActionType.DIVIDEND and self.dividend_cash is None:
            raise ValueError("dividend action requires dividend_cash")
        return self
