"""Run Phase 2B baselines against existing local market and feature datasets."""
from __future__ import annotations

import argparse
from datetime import date

from investment_system.backtesting import BacktestConfig, HistoricalBacktestEngine
from investment_system.backtesting.baseline_runner import (
    run_baseline_strategy, write_baseline_reports,
)
from investment_system.backtesting.strategies import (
    EqualWeightStrategy, SimpleMomentumStrategy, SpyBuyAndHoldStrategy,
)
from investment_system.core.config import load_settings
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.storage.market_store import MarketDataStore
from investment_system.data.universe import load_universe


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2010, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat)
    parser.add_argument(
        "--strategy",
        action="append",
        choices=("spy", "equal_weight", "momentum"),
        help="Repeat to select multiple strategies; omit to run all.",
    )
    parser.add_argument("--initial-cash", type=float, default=100_000)
    parser.add_argument("--commission-bps", type=float, default=0)
    parser.add_argument("--slippage-bps", type=float, default=0)
    parser.add_argument(
        "--output-dir",
        default="data/reports/backtests/baselines",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    settings, universe = load_settings(), load_universe()
    market_store = MarketDataStore(settings.paths.raw, settings.paths.processed)
    feature_store = QuantitativeFeatureStore(
        settings.paths.features, settings.paths.features.parent / "targets",
    )
    calendar = XNYSTradingCalendar()
    end = args.end or market_store.latest_trading_date(universe.benchmark)
    if end is None:
        raise ValueError(f"no local market data for {universe.benchmark}")
    config = BacktestConfig(
        initial_cash=args.initial_cash,
        commission_bps=args.commission_bps,
        slippage_bps=args.slippage_bps,
        benchmark_ticker=universe.benchmark,
    )
    common = {
        "timezone_name": settings.market.timezone,
        "decision_cutoff": settings.market.decision_cutoff,
    }
    strategies = {
        "spy": SpyBuyAndHoldStrategy(
            market_store, calendar, ticker=universe.benchmark, **common,
        ),
        "equal_weight": EqualWeightStrategy(
            feature_store, universe, calendar, **common,
        ),
        "momentum": SimpleMomentumStrategy(
            feature_store, universe, calendar, **common,
        ),
    }
    selected = args.strategy or list(strategies)
    reports = []
    for name in selected:
        engine = HistoricalBacktestEngine(
            config,
            market_store,
            calendar,
            market_timezone=settings.market.timezone,
            decision_cutoff=settings.market.decision_cutoff,
        )
        report = run_baseline_strategy(
            strategies[name], start=args.start, end=end, engine=engine,
            market_store=market_store, calendar=calendar,
        )
        reports.append(report)
        status = report["status"]
        detail = report.get("error", report.get("run_id", ""))
        print(f"{name}: {status} {detail}")
    paths = write_baseline_reports(reports, args.output_dir)
    print(f"wrote {len(paths)} report files to {args.output_dir}")
    return 0 if all(report["status"] == "completed" for report in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
