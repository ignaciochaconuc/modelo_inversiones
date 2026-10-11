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

class FeatureSettings(BaseModel):
    raw_history_start: str = "2009-01-01"
    feature_history_start: str = "2010-01-01"
    schema_version: str = "3"
    quantitative_version: str = "quantitative-v1.1"
    target_version: str = "corporate-action-safe-target-v3"
    minimum_rank_assets: int = Field(default=20, ge=2)

class NewsProviderSettings(BaseModel):
    name: str = "finnhub"
    base_url: str = "https://finnhub.io/api/v1"
    timeout_seconds: float = Field(default=20, gt=0)
    max_retries: int = Field(default=2, ge=0)
    retry_backoff_seconds: float = Field(default=0.5, ge=0)

class NewsSettings(BaseModel):
    schema_version: str = "news-schema-v1"
    normalizer_version: str = "news-normalizer-v1"
    historical_availability_policy: str = "strict_first_seen"
    provider: NewsProviderSettings = NewsProviderSettings()

class Settings(BaseModel):
    decision_timing: str = "after_close"
    prediction_horizon_days: int = Field(default=10, gt=0)
    execution_timing: str = "next_market_open"
    paths: DataPaths
    market: MarketSettings = MarketSettings()
    providers: ProviderSettings = ProviderSettings()
    ingestion: IngestionSettings = IngestionSettings()
    features: FeatureSettings = FeatureSettings()

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

def load_news_settings(config_dir: str | Path | None = None) -> NewsSettings:
    """Load Phase 4A config separately so Phase 3 frozen config hashes stay unchanged."""
    load_dotenv()
    root = Path(config_dir or os.getenv("INVESTMENT_CONFIG_DIR", "config"))
    return NewsSettings.model_validate(load_yaml(root / "news.yaml"))
