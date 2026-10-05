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

class Settings(BaseModel):
    market_timezone: str = "America/New_York"
    decision_timing: str = "after_close"
    prediction_horizon_days: int = Field(default=10, gt=0)
    execution_timing: str = "next_market_open"
    paths: DataPaths

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
