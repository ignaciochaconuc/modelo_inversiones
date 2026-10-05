from datetime import date, datetime, timedelta, timezone

from investment_system.data.ingestion import MarketDataIngestionService
from investment_system.data.schemas.market import MarketBar
from investment_system.data.sources.base import BaseDataSource
from investment_system.data.storage.market_store import MarketDataStore

NOW = datetime(2025, 1, 10, tzinfo=timezone.utc)

def make_bar(day: date, close: float, *, split: float = 1, dividend: float = 0) -> MarketBar:
    return MarketBar(ticker="AAPL", trading_date=day, provider="tiingo", open=close, high=close, low=close, close=close, volume=100, split_factor=split, dividend_cash=dividend, observed_at=NOW, available_at=NOW, ingested_at=NOW)

class FakeSource(BaseDataSource):
    def __init__(self, bars: list[MarketBar]) -> None:
        self.bars = bars
        self.calls: list[tuple[str, date, date]] = []
    def fetch_daily_bars(self, ticker: str, start_date: date, end_date: date) -> list[MarketBar]:
        self.calls.append((ticker, start_date, end_date))
        return [bar for bar in self.bars if start_date <= bar.trading_date <= end_date]

class WeekdayCalendar:
    def is_session(self, value: date) -> bool: return value.weekday() < 5
    def previous_session(self, value: date) -> date:
        value -= timedelta(days=1)
        while not self.is_session(value): value -= timedelta(days=1)
        return value
    def next_session(self, value: date) -> date:
        value += timedelta(days=1)
        while not self.is_session(value): value += timedelta(days=1)
        return value
    def session_open(self, value: date): return NOW
    def session_close(self, value: date): return NOW

def test_empty_history_incremental_overlap_and_idempotency(tmp_path) -> None:
    bars = [make_bar(date(2025, 1, 6), 100), make_bar(date(2025, 1, 7), 101, dividend=0.5), make_bar(date(2025, 1, 8), 51, split=2)]
    source = FakeSource(bars)
    store = MarketDataStore(tmp_path / "raw", tmp_path / "processed")
    service = MarketDataIngestionService(source, store, WeekdayCalendar(), refresh_overlap_days=2)

    first = service.ingest_ticker("AAPL", date(2025, 1, 6), date(2025, 1, 8))
    assert first.effective_start == date(2025, 1, 6)
    assert len(store.read_bars("AAPL")) == 3
    assert len(store.read_actions("AAPL")) == 2

    second = service.ingest_ticker("AAPL", date(2025, 1, 6), date(2025, 1, 8))
    assert second.effective_start == date(2025, 1, 6)
    assert source.calls[-1][1] == date(2025, 1, 6)
    assert len(store.read_bars("AAPL")) == 3
    assert len(store.read_actions("AAPL")) == 2
    assert len(store.read_split_adjusted("AAPL")) == 3

def test_overlap_is_bounded_by_requested_start(tmp_path) -> None:
    store = MarketDataStore(tmp_path / "raw", tmp_path / "processed")
    initial_source = FakeSource([make_bar(date(2025, 1, 10), 100)])
    MarketDataIngestionService(initial_source, store, WeekdayCalendar()).ingest_ticker("AAPL", date(2025, 1, 10), date(2025, 1, 10))
    source = FakeSource([])
    service = MarketDataIngestionService(source, store, WeekdayCalendar(), refresh_overlap_days=5)
    summary = service.ingest_ticker("AAPL", date(2025, 1, 1), date(2025, 1, 12))
    assert summary.effective_start == date(2025, 1, 5)
    assert len(store.read_bars("AAPL")) == 1

def test_dry_run_needs_no_source(tmp_path) -> None:
    service = MarketDataIngestionService(None, MarketDataStore(tmp_path / "raw", tmp_path / "processed"), WeekdayCalendar())
    summary = service.ingest_ticker("AAPL", date(2025, 1, 1), date(2025, 1, 2), dry_run=True)
    assert summary.dry_run and summary.downloaded_rows == 0
