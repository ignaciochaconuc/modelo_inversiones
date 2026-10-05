"""Run the Phase 1C pilot for SPY and a deliberately small equity set."""
import argparse
from datetime import date
import json
import os

from investment_system.core.config import load_settings
from investment_system.core.logging import configure_logging
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.ingestion import MarketDataIngestionService
from investment_system.data.pilot import PilotRequest, RealDataPilot
from investment_system.data.sources.tiingo import TiingoEODDataSource
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.universe import load_universe
from investment_system.features.store_builder import QuantitativeFeatureStoreBuilder


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the Phase 1C real-data pilot")
    parser.add_argument("--start", type=parse_date, default=date(2009, 1, 1), help="raw-data start")
    parser.add_argument("--feature-start", type=parse_date, default=date(2010, 1, 1))
    parser.add_argument("--end", type=parse_date, default=date.today())
    parser.add_argument("--tickers", nargs="+", default=["AAPL", "MSFT", "NVDA"])
    parser.add_argument("--benchmark", default="SPY")
    parser.add_argument("--skip-download", action="store_true")
    parser.add_argument("--skip-features", action="store_true")
    parser.add_argument("--with-targets", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    configure_logging()
    settings, universe = load_settings(), load_universe()
    benchmark = args.benchmark.strip().upper()
    tickers = tuple(dict.fromkeys(item.strip().upper() for item in args.tickers if item.strip() and item.strip().upper() != benchmark))
    request = PilotRequest(args.start, args.feature_start, args.end, tickers, benchmark, args.with_targets)
    market_store = MarketDataStore(settings.paths.raw, settings.paths.processed)
    feature_store = QuantitativeFeatureStore(settings.paths.features, settings.paths.features.parent / "targets")
    calendar = XNYSTradingCalendar()
    builder_universe = universe.model_copy(update={"benchmark": benchmark, "tickers": list(tickers)})
    builder = QuantitativeFeatureStoreBuilder(
        market_store, feature_store, calendar, builder_universe,
        market_timezone=settings.market.timezone, decision_cutoff=settings.market.decision_cutoff,
        raw_history_start=args.start, feature_history_start=args.feature_start,
        feature_schema_version=settings.features.schema_version,
        quantitative_feature_version=settings.features.quantitative_version,
        minimum_rank_assets=settings.features.minimum_rank_assets,
    )
    source = None
    if not args.skip_download:
        api_key = os.getenv("TIINGO_API_KEY")
        if not api_key:
            raise SystemExit("TIINGO_API_KEY is not set. Add it to the local .env file or use --skip-download.")
        provider = settings.providers.tiingo
        source = TiingoEODDataSource(api_key, base_url=provider.base_url,
            market_timezone=settings.market.timezone, market_close_time=settings.market.close_time,
            assumed_available_time=provider.assumed_eod_available_time,
            timeout_seconds=provider.timeout_seconds, schema_version=settings.ingestion.schema_version)
    ingestion = MarketDataIngestionService(source, market_store, calendar,
        refresh_overlap_days=settings.ingestion.refresh_overlap_days,
        normalization_version=settings.ingestion.normalization_version,
        throttle_seconds=settings.providers.tiingo.throttle_seconds) if source else None
    pilot = RealDataPilot(
        market_store, feature_store, calendar, builder,
        "data/reports/real_data_pilot.json", ingestion,
        settings_metadata={
            "provider": "tiingo",
            "assumed_eod_available_time": settings.providers.tiingo.assumed_eod_available_time,
            "refresh_overlap_days": settings.ingestion.refresh_overlap_days,
        },
    )
    try:
        report = pilot.run(request, skip_download=args.skip_download, skip_features=args.skip_features)
    finally:
        if source is not None:
            source.close()
    print(json.dumps({"status": report["status"], "report": "data/reports/real_data_pilot.json",
                      **report["global_summary"]}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
