"""Build point-in-time quantitative features from locally ingested market data."""
import argparse
from datetime import date
import json

from investment_system.core.config import load_settings
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.universe import load_universe
from investment_system.features.store_builder import QuantitativeFeatureStoreBuilder

def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from error

def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Build the quantitative feature store")
    target = result.add_mutually_exclusive_group(required=True)
    target.add_argument("--ticker")
    target.add_argument("--universe", action="store_true")
    result.add_argument("--start", type=parse_date)
    result.add_argument("--end", type=parse_date, default=date.today())
    result.add_argument("--with-targets", action="store_true")
    result.add_argument("--dry-run", action="store_true")
    return result

def main() -> int:
    args = parser().parse_args()
    settings = load_settings()
    universe = load_universe()
    start = args.start or date.fromisoformat(settings.features.feature_history_start)
    tickers = universe.tickers if args.universe else [args.ticker.upper()]
    if args.dry_run:
        print(json.dumps({
            "dry_run": True, "tickers": tickers, "benchmark": universe.benchmark,
            "start": start.isoformat(), "end": args.end.isoformat(),
            "with_targets": args.with_targets,
            "features_path": str(settings.paths.features / "quantitative"),
            "targets_path": str(settings.paths.features.parent / "targets" / "quantitative"),
        }))
        return 0
    market_store = MarketDataStore(settings.paths.raw, settings.paths.processed)
    feature_store = QuantitativeFeatureStore(settings.paths.features, settings.paths.features.parent / "targets")
    builder = QuantitativeFeatureStoreBuilder(
        market_store, feature_store, XNYSTradingCalendar(), universe,
        market_timezone=settings.market.timezone, decision_cutoff=settings.market.decision_cutoff,
        raw_history_start=date.fromisoformat(settings.features.raw_history_start),
        feature_history_start=date.fromisoformat(settings.features.feature_history_start),
        feature_schema_version=settings.features.schema_version,
        quantitative_feature_version=settings.features.quantitative_version,
        target_version=settings.features.target_version,
        minimum_rank_assets=settings.features.minimum_rank_assets,
    )
    result = builder.build(tickers, start, args.end, with_targets=args.with_targets)
    print(json.dumps({"dry_run": False, **result.report}, default=str))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
