"""Build and validate the complete fixed Phase 1D development universe."""
import argparse
from datetime import date
import json
import os

from investment_system.core.config import load_settings
from investment_system.core.logging import configure_logging
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.full_universe import FullUniverseBuild, FullUniverseRequest
from investment_system.data.ingestion import MarketDataIngestionService
from investment_system.data.sources.tiingo import TiingoEODDataSource
from investment_system.data.provider_symbols import load_provider_symbols
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
    parser = argparse.ArgumentParser(description="Build the Phase 1D full development universe")
    parser.add_argument("--raw-start", type=parse_date, default=date(2009, 1, 1))
    parser.add_argument("--feature-start", type=parse_date, default=date(2010, 1, 1))
    parser.add_argument("--end", type=parse_date, default=date.today())
    parser.add_argument("--with-targets", action="store_true")
    parser.add_argument("--skip-download", action="store_true", help="use only locally stored raw data")
    parser.add_argument("--skip-features", action="store_true", help="resume ingestion without rebuilding features")
    parser.add_argument("--skip-provider-ticker", action="append", default=[],
                        help="explicitly skip a reviewed provider symbol without inventing a mapping")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    configure_logging()
    settings, universe = load_settings(), load_universe()
    calendar = XNYSTradingCalendar()
    market_store = MarketDataStore(settings.paths.raw, settings.paths.processed)
    feature_store = QuantitativeFeatureStore(settings.paths.features, settings.paths.features.parent / "targets")
    builder = QuantitativeFeatureStoreBuilder(
        market_store, feature_store, calendar, universe,
        market_timezone=settings.market.timezone, decision_cutoff=settings.market.decision_cutoff,
        raw_history_start=args.raw_start, feature_history_start=args.feature_start,
        feature_schema_version=settings.features.schema_version,
        quantitative_feature_version=settings.features.quantitative_version,
        target_version=settings.features.target_version,
        minimum_rank_assets=settings.features.minimum_rank_assets,
    )
    source = None
    if not args.skip_download:
        api_key = os.getenv("TIINGO_API_KEY")
        if not api_key:
            raise SystemExit("TIINGO_API_KEY is not set. Add it to the local .env file or use --skip-download.")
        provider = settings.providers.tiingo
        source = TiingoEODDataSource(
            api_key, base_url=provider.base_url, market_timezone=settings.market.timezone,
            market_close_time=settings.market.close_time,
            assumed_available_time=provider.assumed_eod_available_time,
            timeout_seconds=provider.timeout_seconds, schema_version=settings.ingestion.schema_version,
            symbol_aliases=load_provider_symbols(),
        )
    ingestion = MarketDataIngestionService(
        source, market_store, calendar,
        refresh_overlap_days=settings.ingestion.refresh_overlap_days,
        normalization_version=settings.ingestion.normalization_version,
        throttle_seconds=settings.providers.tiingo.throttle_seconds,
    ) if source else None
    workflow = FullUniverseBuild(
        market_store, feature_store, calendar, universe, builder,
        "data/reports/full_universe_build.json", ingestion,
        settings_metadata={
            "assumed_eod_available_time": settings.providers.tiingo.assumed_eod_available_time,
            "refresh_overlap_days": settings.ingestion.refresh_overlap_days,
            "throttle_seconds": settings.providers.tiingo.throttle_seconds,
            "provider_symbol_aliases": load_provider_symbols().get("tiingo", {}),
        },
    )
    try:
        report = workflow.run(
            FullUniverseRequest(args.raw_start, args.feature_start, args.end, args.with_targets),
            skip_download=args.skip_download, skip_features=args.skip_features,
            skip_provider_tickers=set(args.skip_provider_ticker),
        )
    finally:
        if source is not None:
            source.close()
    print(json.dumps({"status": report["status"], "report": "data/reports/full_universe_build.json",
                      **report["global_summary"]}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
