"""Phase-zero entry point; connect a market data source before use."""
from investment_system.core.config import load_settings
from investment_system.data.storage.parquet_store import ParquetStore

if __name__ == "__main__":
    settings = load_settings()
    ParquetStore(settings.paths.features)
    print(f"Feature store initialized at {settings.paths.features}")
