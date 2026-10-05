from dataclasses import dataclass
from datetime import date, timedelta
import logging
import time
import pandas as pd

from investment_system.data.calendar import TradingCalendar
from investment_system.data.normalization import build_latest_basis_split_adjusted_series, extract_corporate_actions
from investment_system.data.sources.base import BaseDataSource
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.validation.market import unexpected_session_gaps, validate_market_bars

logger = logging.getLogger(__name__)

@dataclass(frozen=True)
class IngestionSummary:
    ticker: str
    requested_start: date
    effective_start: date
    end_date: date
    downloaded_rows: int
    saved_rows: int
    corporate_actions: int
    normalized_rows: int
    unexpected_gaps: tuple[date, ...]
    missing_refreshed_dates: tuple[date, ...]
    dry_run: bool = False

class MarketDataIngestionService:
    def __init__(self, source: BaseDataSource | None, store: MarketDataStore, calendar: TradingCalendar, *, refresh_overlap_days: int = 5, normalization_version: str = "split-adjusted-latest-v1", throttle_seconds: float = 0) -> None:
        if refresh_overlap_days < 0 or throttle_seconds < 0:
            raise ValueError("overlap and throttle must be non-negative")
        self.source, self.store, self.calendar = source, store, calendar
        self.refresh_overlap_days = refresh_overlap_days
        self.normalization_version = normalization_version
        self.throttle_seconds = throttle_seconds

    def effective_start_date(self, ticker: str, requested_start: date) -> date:
        latest = self.store.latest_trading_date(ticker)
        return requested_start if latest is None else max(requested_start, latest - timedelta(days=self.refresh_overlap_days))

    def ingest_ticker(self, ticker: str, start_date: date, end_date: date, *, dry_run: bool = False) -> IngestionSummary:
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")
        ticker = ticker.strip().upper()
        effective_start = self.effective_start_date(ticker, start_date)
        if dry_run:
            return IngestionSummary(ticker, start_date, effective_start, end_date, 0, 0, 0, 0, (), (), True)
        if self.source is None:
            raise ValueError("a data source is required unless dry_run=True")
        started = time.monotonic()
        existing = self.store.read_bars(ticker)
        bars = validate_market_bars(self.source.fetch_daily_bars(ticker, effective_start, end_date))
        if any(bar.ticker != ticker for bar in bars):
            raise ValueError("provider returned a bar for a different ticker")
        existing_dates: set[date] = set()
        if not existing.empty:
            existing_dates = set(pd.to_datetime(existing["trading_date"]).dt.date)
            existing_dates = {value for value in existing_dates if effective_start <= value <= end_date}
        returned_dates = {bar.trading_date for bar in bars}
        missing_refreshed_dates = tuple(sorted(existing_dates - returned_dates))
        if missing_refreshed_dates:
            logger.warning("market_data_reconciliation ticker=%s missing_refreshed_dates=%s retained=true", ticker, ",".join(item.isoformat() for item in missing_refreshed_dates))
        gaps = tuple(unexpected_session_gaps(bars, effective_start, end_date, self.calendar))
        saved = self.store.upsert_bars(bars)
        actions = extract_corporate_actions(bars)
        self.store.replace_actions_for_dates(ticker, {bar.trading_date for bar in bars}, actions)
        raw = self.store.read_bars(ticker)
        stored_actions = self.store.read_actions(ticker)
        normalized = build_latest_basis_split_adjusted_series(raw, stored_actions, self.normalization_version)
        normalized_rows = self.store.write_latest_basis_split_adjusted(ticker, normalized)
        logger.info("market_data_ingestion ticker=%s start=%s end=%s downloaded=%d saved=%d actions=%d normalized=%d gaps=%d elapsed_ms=%.1f", ticker, effective_start, end_date, len(bars), saved, len(actions), normalized_rows, len(gaps), (time.monotonic() - started) * 1000)
        return IngestionSummary(ticker, start_date, effective_start, end_date, len(bars), saved, len(actions), normalized_rows, gaps, missing_refreshed_dates)

    def ingest_many(self, tickers: list[str], start_date: date, end_date: date, *, dry_run: bool = False) -> list[IngestionSummary]:
        summaries: list[IngestionSummary] = []
        for index, ticker in enumerate(tickers):
            summaries.append(self.ingest_ticker(ticker, start_date, end_date, dry_run=dry_run))
            if not dry_run and self.throttle_seconds and index < len(tickers) - 1:
                time.sleep(self.throttle_seconds)
        return summaries
