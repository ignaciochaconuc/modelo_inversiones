from pathlib import Path
from pydantic import BaseModel, Field, model_validator
from investment_system.core.config import load_yaml

class UniverseMetadata(BaseModel):
    name: str
    point_in_time: bool
    survivorship_bias_warning: bool
    as_of: str

class UniverseConfig(BaseModel):
    benchmark: str = Field(min_length=1)
    asset_class: str
    universe_type: str
    description: str
    universe: UniverseMetadata
    tickers: list[str] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_universe(self) -> "UniverseConfig":
        if len(self.tickers) != len(set(self.tickers)):
            raise ValueError("universe contains duplicate tickers")
        if self.benchmark in self.tickers:
            raise ValueError("benchmark must be separate from investable tickers")
        if not self.universe.point_in_time and not self.universe.survivorship_bias_warning:
            raise ValueError("a non-point-in-time universe must declare survivorship bias")
        return self

def load_universe(path: str | Path = "config/universe.yaml") -> UniverseConfig:
    return UniverseConfig.model_validate(load_yaml(path))
