from datetime import date
from pathlib import Path

import pandas as pd

from investment_system.data.schemas.market import CorporateAction, MarketBar

class MarketDataStore:
    """Idempotent per-ticker Parquet storage for Phase 1A."""
    def __init__(self, raw_root: str | Path, processed_root: str | Path) -> None:
        self.raw_daily = Path(raw_root) / "tiingo" / "daily"
        self.actions = Path(raw_root) / "tiingo" / "corporate_actions"
        self.latest_basis_split_adjusted = Path(processed_root) / "market" / "split_adjusted_latest"
        for path in (self.raw_daily, self.actions, self.latest_basis_split_adjusted):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _ticker_file(root: Path, ticker: str) -> Path:
        safe = ticker.upper().replace("/", "_")
        return root / f"{safe}.parquet"

    @staticmethod
    def _read(path: Path) -> pd.DataFrame:
        return pd.read_parquet(path) if path.exists() else pd.DataFrame()

    @staticmethod
    def _write_atomic(frame: pd.DataFrame, path: Path) -> None:
        temporary = path.with_suffix(".tmp.parquet")
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)

    def read_bars(self, ticker: str) -> pd.DataFrame:
        return self._read(self._ticker_file(self.raw_daily, ticker))

    def read_actions(self, ticker: str) -> pd.DataFrame:
        return self._read(self._ticker_file(self.actions, ticker))

    def read_latest_basis_split_adjusted(self, ticker: str) -> pd.DataFrame:
        return self._read(self._ticker_file(self.latest_basis_split_adjusted, ticker))

    def read_split_adjusted(self, ticker: str) -> pd.DataFrame:
        """Backward-compatible alias; returns latest-basis, not point-in-time data."""
        return self.read_latest_basis_split_adjusted(ticker)

    def latest_trading_date(self, ticker: str) -> date | None:
        frame = self.read_bars(ticker)
        if frame.empty:
            return None
        return pd.to_datetime(frame["trading_date"]).max().date()

    def upsert_bars(self, bars: list[MarketBar]) -> int:
        if not bars:
            return 0
        ticker = bars[0].ticker
        if any(bar.ticker != ticker for bar in bars):
            raise ValueError("upsert_bars accepts one ticker at a time")
        incoming = pd.DataFrame([bar.model_dump(mode="python") for bar in bars])
        existing = self.read_bars(ticker)
        combined = pd.concat([existing, incoming], ignore_index=True)
        combined = combined.sort_values("ingested_at").drop_duplicates(
            ["ticker", "trading_date", "provider"], keep="last"
        ).sort_values("trading_date")
        self._write_atomic(combined, self._ticker_file(self.raw_daily, ticker))
        return len(incoming)

    def replace_actions_for_dates(
        self, ticker: str, refreshed_dates: set[date], actions: list[CorporateAction]
    ) -> int:
        existing = self.read_actions(ticker)
        if not existing.empty and refreshed_dates:
            existing_dates = pd.to_datetime(existing["effective_date"]).dt.date
            existing = existing[~existing_dates.isin(refreshed_dates)]
        incoming = pd.DataFrame([action.model_dump(mode="python") for action in actions])
        combined = pd.concat([existing, incoming], ignore_index=True)
        if combined.empty:
            path = self._ticker_file(self.actions, ticker)
            if path.exists():
                self._write_atomic(combined, path)
            return 0
        combined = combined.sort_values("ingested_at").drop_duplicates(
            ["ticker", "effective_date", "action_type", "provider"], keep="last"
        ).sort_values(["effective_date", "action_type"])
        self._write_atomic(combined, self._ticker_file(self.actions, ticker))
        return len(incoming)

    def write_latest_basis_split_adjusted(self, ticker: str, frame: pd.DataFrame) -> int:
        if frame.empty:
            return 0
        self._write_atomic(frame, self._ticker_file(self.latest_basis_split_adjusted, ticker))
        return len(frame)

    def write_split_adjusted(self, ticker: str, frame: pd.DataFrame) -> int:
        """Backward-compatible alias; persists the latest-basis artifact."""
        return self.write_latest_basis_split_adjusted(ticker, frame)
