"""Ingest Tiingo EOD data into local raw and split-adjusted Parquet stores."""
import argparse
from datetime import date
import json
import os

from investment_system.core.config import load_settings
from investment_system.core.logging import configure_logging
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.ingestion import MarketDataIngestionService
from investment_system.data.sources.tiingo import TiingoEODDataSource
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.universe import load_universe

def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from error

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest daily Tiingo market data")
    target = parser.add_mutually_exclusive_group(required=True)
    target.add_argument("--ticker", help="single ticker, for example AAPL")
    target.add_argument("--universe", action="store_true", help="development universe plus benchmark")
    parser.add_argument("--start", required=True, type=parse_date)
    parser.add_argument("--end", type=parse_date, default=date.today())
    parser.add_argument("--dry-run", action="store_true", help="show effective ranges without HTTP calls")
    return parser

def main() -> int:
    args = build_parser().parse_args()
    configure_logging()
    settings = load_settings()
    universe = load_universe()
    tickers = [args.ticker.upper()] if args.ticker else [universe.benchmark, *universe.tickers]
    store = MarketDataStore(settings.paths.raw, settings.paths.processed)
    source = None
    if not args.dry_run:
        api_key = os.getenv("TIINGO_API_KEY")
        if not api_key:
            raise SystemExit("TIINGO_API_KEY is not set. Add it to the local .env file or use --dry-run.")
        provider = settings.providers.tiingo
        source = TiingoEODDataSource(
            api_key, base_url=provider.base_url, market_timezone=settings.market.timezone,
            market_close_time=settings.market.close_time,
            assumed_available_time=provider.assumed_eod_available_time,
            timeout_seconds=provider.timeout_seconds,
            schema_version=settings.ingestion.schema_version,
        )
    service = MarketDataIngestionService(
        source, store, XNYSTradingCalendar(),
        refresh_overlap_days=settings.ingestion.refresh_overlap_days,
        normalization_version=settings.ingestion.normalization_version,
        throttle_seconds=settings.providers.tiingo.throttle_seconds,
    )
    try:
        summaries = service.ingest_many(tickers, args.start, args.end, dry_run=args.dry_run)
    finally:
        if source is not None:
            source.close()
    for summary in summaries:
        print(json.dumps({**summary.__dict__, "requested_start": summary.requested_start.isoformat(), "effective_start": summary.effective_start.isoformat(), "end_date": summary.end_date.isoformat(), "unexpected_gaps": [item.isoformat() for item in summary.unexpected_gaps]}))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
