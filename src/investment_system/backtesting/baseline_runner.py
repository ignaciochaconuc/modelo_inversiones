"""Explicit orchestration and persistence for Phase 2B baseline backtests."""
from __future__ import annotations

from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Any

from investment_system.backtesting.engine import (
    BacktestDataError, HistoricalBacktestEngine, UnmodelledCorporateActionError,
)
from investment_system.backtesting.reporting import BenchmarkDataError, build_backtest_report
from investment_system.backtesting.strategies import BaselineStrategy
from investment_system.data.calendar import TradingCalendar
from investment_system.data.storage.market_store import MarketDataStore


def _run_id(strategy: BaselineStrategy, start: date, end: date, config: dict[str, Any]) -> str:
    payload = json.dumps(
        [strategy.strategy_name, strategy.strategy_version, start, end, config],
        sort_keys=True,
        default=str,
        separators=(",", ":"),
    )
    return f"baseline_{hashlib.sha256(payload.encode()).hexdigest()[:20]}"


def run_baseline_strategy(
    strategy: BaselineStrategy,
    *,
    start: date,
    end: date,
    engine: HistoricalBacktestEngine,
    market_store: MarketDataStore,
    calendar: TradingCalendar,
) -> dict[str, Any]:
    """Generate, simulate, and report one baseline without hiding invalid runs."""
    base: dict[str, Any] = {
        "strategy_name": strategy.strategy_name,
        "strategy_version": strategy.strategy_version,
        "requested_start": start.isoformat(),
        "requested_end": end.isoformat(),
    }
    try:
        plan = strategy.generate_allocations(start, end)
        run_id = _run_id(
            strategy, start, end, engine.config.model_dump(mode="json"),
        )
        result = engine.run(start, end, plan.allocations, run_id=run_id)
        metrics = build_backtest_report(
            result, market_store=market_store, calendar=calendar,
        )
        return {
            **base,
            "status": "completed",
            "run_id": result.run_id,
            "allocation_count": len(plan.allocations),
            "eligibility_summary": plan.eligibility_summary(),
            "metrics": metrics.model_dump(mode="json"),
        }
    except UnmodelledCorporateActionError as error:
        return {
            **base,
            "status": "failed",
            "error_type": type(error).__name__,
            "error": str(error),
            "ticker": error.ticker,
            "event_date": error.event_date.isoformat(),
            "event_id": error.event_id,
            "reason": error.reason,
        }
    except (BacktestDataError, BenchmarkDataError, ValueError) as error:
        return {
            **base,
            "status": "failed",
            "error_type": type(error).__name__,
            "error": str(error),
        }


def build_baseline_comparison(reports: list[dict[str, Any]]) -> dict[str, Any]:
    """Return comparable fields without ranking or declaring a winner."""
    comparison: dict[str, Any] = {
        "comparison_version": "baseline-comparison-v1",
        "strategies": {},
        "failures": {},
    }
    for report in reports:
        name = report["strategy_name"]
        if report["status"] != "completed":
            comparison["failures"][name] = {
                key: report.get(key)
                for key in ("error_type", "error", "ticker", "event_date", "event_id", "reason")
                if report.get(key) is not None
            }
            continue
        metrics = report["metrics"]
        performance = metrics["performance"]
        comparison["strategies"][name] = {
            "strategy_version": report["strategy_version"],
            "run_id": report["run_id"],
            "cumulative_return": performance["cumulative_return"],
            "cagr": performance["cagr"],
            "sharpe_ratio": performance["sharpe_ratio"],
            "sortino_ratio": performance["sortino_ratio"],
            "max_drawdown": performance["max_drawdown"],
            "annualized_volatility": performance["annualized_volatility"],
            "total_turnover": metrics["costs"]["total_turnover"],
            "total_transaction_cost": metrics["costs"]["total_transaction_cost"],
            "average_cash_weight": metrics["exposure"]["average_cash_weight"],
        }
    return comparison


def write_baseline_reports(
    reports: list[dict[str, Any]],
    output_dir: str | Path,
) -> list[Path]:
    """Persist reports only when explicitly called by a runner or user."""
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []
    for report in reports:
        path = destination / f"{report['strategy_name']}.json"
        path.write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        paths.append(path)
    comparison_path = destination / "comparison.json"
    comparison_path.write_text(
        json.dumps(
            build_baseline_comparison(reports),
            indent=2,
            sort_keys=True,
            default=str,
        ),
        encoding="utf-8",
    )
    paths.append(comparison_path)
    return paths
