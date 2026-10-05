from datetime import datetime
from pydantic import BaseModel, ConfigDict, model_validator

class PointInTimeRecord(BaseModel):
    """Availability metadata shared by external observations."""
    model_config = ConfigDict(extra="forbid")
    observed_at: datetime | None = None
    published_at: datetime | None = None
    available_at: datetime | None = None
    ingested_at: datetime

    @model_validator(mode="after")
    def validate_timestamps(self) -> "PointInTimeRecord":
        values = [v for v in (self.observed_at, self.published_at, self.available_at, self.ingested_at) if v]
        if any(v.tzinfo is None for v in values):
            raise ValueError("point-in-time timestamps must be timezone-aware")
        return self
