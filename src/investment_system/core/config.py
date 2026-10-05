from pathlib import Path
from typing import Any
import os
import yaml
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from investment_system.core.exceptions import ConfigurationError

class DataPaths(BaseModel):
    raw: Path
    processed: Path
    features: Path
    cache: Path
    logs: Path

class MarketSettings(BaseModel):
    timezone: str = "America/New_York"
    close_time: str = "16:00"
    decision_cutoff: str = "20:15"

class TiingoSettings(BaseModel):
    base_url: str = "https://api.tiingo.com/tiingo/daily"
    assumed_eod_available_time: str = "20:00"
    timeout_seconds: float = Field(default=20, gt=0)
    throttle_seconds: float = Field(default=0.25, ge=0)

class ProviderSettings(BaseModel):
    tiingo: TiingoSettings = TiingoSettings()

class IngestionSettings(BaseModel):
    refresh_overlap_days: int = Field(default=5, ge=0)
    schema_version: str = "1"
    normalization_version: str = "split-adjusted-latest-v1"

class Settings(BaseModel):
    decision_timing: str = "after_close"
    prediction_horizon_days: int = Field(default=10, gt=0)
    execution_timing: str = "next_market_open"
    paths: DataPaths
    market: MarketSettings = MarketSettings()
    providers: ProviderSettings = ProviderSettings()
    ingestion: IngestionSettings = IngestionSettings()

    @property
    def market_timezone(self) -> str:
        """Backward-compatible alias for the original flat setting."""
        return self.market.timezone

def load_yaml(path: str | Path) -> dict[str, Any]:
    path = Path(path)
    if not path.exists():
        raise ConfigurationError(f"configuration file not found: {path}")
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream) or {}

def load_settings(config_dir: str | Path | None = None) -> Settings:
    load_dotenv()
    root = Path(config_dir or os.getenv("INVESTMENT_CONFIG_DIR", "config"))
    return Settings.model_validate(load_yaml(root / "settings.yaml"))
