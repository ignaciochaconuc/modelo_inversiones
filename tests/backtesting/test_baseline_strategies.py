from __future__ import annotations

from datetime import date, datetime
import json
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from investment_system.backtesting import (
    BacktestConfig, HistoricalBacktestEngine, build_backtest_report,
    simulate_benchmark,
)
from investment_system.backtesting.baseline_runner import (
    build_baseline_comparison, run_baseline_strategy,
)
from investment_system.backtesting.strategies import (
    EqualWeightStrategy, SimpleMomentumStrategy, SpyBuyAndHoldStrategy,
)
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.universe import UniverseConfig


NY = ZoneInfo("America/New_York")


class RecordingFeatureStore:
    def __init__(self, rows: pd.DataFrame) -> None:
        self.rows = rows
        self.requests: list[list[str]] = []

    def read_feature_range(
        self, start: date, end: date, *, columns: list[str], tickers: list[str] | None = None,
    ) -> pd.DataFrame:
        self.requests.append(columns)
        selected = list(dict.fromkeys(("ticker", "decision_date", *columns)))
        frame = self.rows.copy()
        dates = pd.to_datetime(frame["decision_date"]).dt.date
        frame = frame[(dates >= start) & (dates <= end)]
        if tickers is not None:
            frame = frame[frame["ticker"].isin(tickers)]
        return frame[selected].sort_values(["decision_date", "ticker"]).reset_index(drop=True)


class MemoryMarketStore:
    def __init__(
        self,
        bars: dict[str, pd.DataFrame],
        actions: dict[str, pd.DataFrame] | None = None,
        events: pd.DataFrame | None = None,
    ) -> None:
        self.bars = bars
        self.actions = actions or {}
        self.events = events if events is not None else pd.DataFrame()

    def read_bars(self, ticker: str) -> pd.DataFrame:
        return self.bars.get(ticker, pd.DataFrame()).copy()

    def read_actions(self, ticker: str) -> pd.DataFrame:
        return self.actions.get(ticker, pd.DataFrame()).copy()

    def read_corporate_action_events(self) -> pd.DataFrame:
        return self.events.copy()


def universe(tickers: list[str]) -> UniverseConfig:
    return UniverseConfig.model_validate({
        "benchmark": "SPY",
        "asset_class": "US_EQUITY",
        "universe_type": "development_fixed",
        "description": "synthetic fixed universe",
        "universe": {
            "name": "test", "point_in_time": False,
            "survivorship_bias_warning": True, "as_of": "2026-10-05",
        },
        "tickers": tickers,
    })


def feature_row(
    ticker: str,
    day: date,
    *,
    eligible: bool = True,
    momentum: float | None = 0,
    target_rank: float = 0.99,
) -> dict:
    return {
        "ticker": ticker,
        "decision_date": day,
        "decision_time": datetime(day.year, day.month, day.day, 20, 15, tzinfo=NY),
        "model_eligible": eligible,
        "momentum_20d": momentum,
        "target_rank_10d": target_rank,
    }


def bar(ticker: str, day: date, open_: float, close: float) -> dict:
    return {
        "ticker": ticker,
        "trading_date": day,
        "open": open_,
        "close": close,
        "available_at": datetime(day.year, day.month, day.day, 20, tzinfo=NY),
    }


def frame(ticker: str, days: list[date], prices: list[tuple[float, float]]) -> pd.DataFrame:
    return pd.DataFrame([
        bar(ticker, day, open_, close)
        for day, (open_, close) in zip(days, prices, strict=True)
    ])


def engine(store: MemoryMarketStore, cash: float = 1_000) -> HistoricalBacktestEngine:
    return HistoricalBacktestEngine(
        BacktestConfig(initial_cash=cash), store, XNYSTradingCalendar(),
    )


def test_equal_weight_is_deterministic_causal_and_never_requests_targets() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    rows = pd.DataFrame([
        feature_row("A", d1), feature_row("B", d1),
        feature_row("A", d2, eligible=False), feature_row("B", d2),
    ])
    store = RecordingFeatureStore(rows)
    strategy = EqualWeightStrategy(store, universe(["A", "B"]), XNYSTradingCalendar())
    first = strategy.generate_allocations(d1, d1)
    second = strategy.generate_allocations(d1, d1)
    assert first == second
    assert first.allocations[d1].weights == {"A": 0.5, "B": 0.5}
    assert first.allocations[d1].generated_at == datetime(2025, 1, 2, 20, 15, tzinfo=NY)
    assert sum(first.allocations[d1].weights.values()) + first.allocations[d1].cash_weight == 1
    assert all(not column.startswith("target_") for request in store.requests for column in request)


def test_equal_weight_four_and_one_hundred_assets_are_exactly_equal() -> None:
    day = date(2025, 1, 2)
    for count, expected in ((4, 0.25), (100, 0.01)):
        tickers = [f"A{index:03d}" for index in range(count)]
        strategy = EqualWeightStrategy(
            RecordingFeatureStore(pd.DataFrame([feature_row(ticker, day) for ticker in tickers])),
            universe(tickers), XNYSTradingCalendar(),
        )
        allocation = strategy.generate_allocations(day, day).allocations[day]
        assert len(allocation.weights) == count
        assert all(weight == pytest.approx(expected) for weight in allocation.weights.values())
        assert allocation.cash_weight == 0


def test_equal_weight_excludes_ineligible_missing_and_spy_rows() -> None:
    day = date(2025, 1, 2)
    rows = pd.DataFrame([
        feature_row("A", day), feature_row("B", day, eligible=False),
        feature_row("SPY", day),
    ])
    strategy = EqualWeightStrategy(
        RecordingFeatureStore(rows), universe(["A", "B", "C"]), XNYSTradingCalendar(),
    )
    allocation = strategy.generate_allocations(day, day).allocations[day]
    assert allocation.weights == {"A": 1.0}
    assert "B" not in allocation.weights
    assert "C" not in allocation.weights
    assert "SPY" not in allocation.weights


def test_equal_weight_zero_eligible_is_all_cash() -> None:
    day = date(2025, 1, 2)
    strategy = EqualWeightStrategy(
        RecordingFeatureStore(pd.DataFrame([feature_row("A", day, eligible=False)])),
        universe(["A"]), XNYSTradingCalendar(),
    )
    allocation = strategy.generate_allocations(day, day).allocations[day]
    assert allocation.weights == {}
    assert allocation.cash_weight == 1


def test_future_eligibility_changes_only_the_future_allocation() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    rows = pd.DataFrame([
        feature_row("A", d1), feature_row("B", d1),
        feature_row("A", d2), feature_row("B", d2, eligible=False),
    ])
    strategy = EqualWeightStrategy(
        RecordingFeatureStore(rows), universe(["A", "B"]), XNYSTradingCalendar(),
    )
    plan = strategy.generate_allocations(d1, d2)
    assert plan.allocations[d1].weights == {"A": 0.5, "B": 0.5}
    assert plan.allocations[d2].weights == {"A": 1.0}


def test_momentum_selects_exact_top_ten_with_deterministic_tie_break() -> None:
    day = date(2025, 1, 2)
    tickers = [f"A{index:02d}" for index in range(12)]
    values = {ticker: float(index) for index, ticker in enumerate(tickers)}
    values["A01"] = values["A02"] = 20.0
    rows = pd.DataFrame([
        feature_row(ticker, day, momentum=values[ticker]) for ticker in reversed(tickers)
    ])
    strategy = SimpleMomentumStrategy(
        RecordingFeatureStore(rows), universe(tickers), XNYSTradingCalendar(),
    )
    allocation = strategy.generate_allocations(day, day).allocations[day]
    expected = sorted(tickers, key=lambda ticker: (-values[ticker], ticker))[:10]
    assert list(allocation.weights) == expected
    assert len(allocation.weights) == 10
    assert all(weight == 0.10 for weight in allocation.weights.values())
    assert allocation.cash_weight == 0


def test_momentum_seven_assets_invests_seventy_percent() -> None:
    day = date(2025, 1, 2)
    tickers = [f"A{index}" for index in range(7)]
    rows = pd.DataFrame([
        feature_row(ticker, day, momentum=float(index)) for index, ticker in enumerate(tickers)
    ])
    allocation = SimpleMomentumStrategy(
        RecordingFeatureStore(rows), universe(tickers), XNYSTradingCalendar(),
    ).generate_allocations(day, day).allocations[day]
    assert len(allocation.weights) == 7
    assert sum(allocation.weights.values()) == pytest.approx(0.7)
    assert allocation.cash_weight == pytest.approx(0.3)


def test_momentum_excludes_spy_ineligible_and_nonfinite_values_without_imputation() -> None:
    day = date(2025, 1, 2)
    rows = pd.DataFrame([
        feature_row("A", day, momentum=1),
        feature_row("B", day, momentum=100, eligible=False),
        feature_row("C", day, momentum=float("nan")),
        feature_row("D", day, momentum=float("inf")),
        feature_row("SPY", day, momentum=1_000),
    ])
    store = RecordingFeatureStore(rows)
    allocation = SimpleMomentumStrategy(
        store, universe(["A", "B", "C", "D"]), XNYSTradingCalendar(),
    ).generate_allocations(day, day).allocations[day]
    assert allocation.weights == {"A": 0.1}
    assert allocation.cash_weight == 0.9
    assert all("target_rank_10d" not in request for request in store.requests)


def test_future_momentum_and_target_rank_never_change_historical_selection() -> None:
    d1, d2 = date(2025, 1, 2), date(2025, 1, 3)
    rows = pd.DataFrame([
        feature_row("A", d1, momentum=2, target_rank=0),
        feature_row("B", d1, momentum=1, target_rank=1),
        feature_row("A", d2, momentum=-100, target_rank=1),
        feature_row("B", d2, momentum=100, target_rank=0),
    ])
    strategy = SimpleMomentumStrategy(
        RecordingFeatureStore(rows), universe(["A", "B"]), XNYSTradingCalendar(),
    )
    historical = strategy.generate_allocations(d1, d1).allocations[d1]
    assert list(historical.weights) == ["A", "B"]
    assert historical.weights == {"A": 0.1, "B": 0.1}


def test_feature_store_api_refuses_target_columns(tmp_path) -> None:
    store = QuantitativeFeatureStore(tmp_path / "features", tmp_path / "targets")
    with pytest.raises(ValueError, match="target columns"):
        store.read_feature_range(
            date(2025, 1, 1), date(2025, 1, 2), columns=["target_rank_10d"],
        )


def test_spy_strategy_matches_internal_benchmark_with_dividend_split_and_raw_prices() -> None:
    days = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6), date(2025, 1, 7)]
    spy = frame("SPY", days, [(100, 100), (100, 100), (50, 50), (50, 50)])
    spy["adjusted_open"] = [1, 1, 1, 1]
    spy["adjusted_close"] = [1, 1, 1, 1]
    actions = pd.DataFrame([
        {"ticker": "SPY", "effective_date": days[2], "action_type": "split",
         "split_factor": 2, "dividend_cash": None},
        {"ticker": "SPY", "effective_date": days[2], "action_type": "dividend",
         "split_factor": None, "dividend_cash": 0.5},
    ])
    store = MemoryMarketStore({"SPY": spy}, {"SPY": actions})
    calendar = XNYSTradingCalendar()
    strategy = SpyBuyAndHoldStrategy(store, calendar)
    plan = strategy.generate_allocations(days[0], days[-1])
    assert plan.allocations[days[0]].weights == {"SPY": 1.0}
    assert set(plan.allocations) == {days[0], days[2]}

    result = engine(store).run(days[0], days[-1], plan.allocations)
    benchmark = simulate_benchmark(result, store, calendar)
    assert result.fills[0].filled_at.date() == days[1]
    assert result.snapshots[0].positions == []
    assert result.snapshots[-1].positions[0].quantity == pytest.approx(20.2)
    assert [snapshot.nav for snapshot in result.snapshots] == pytest.approx(
        [snapshot.nav for snapshot in benchmark.snapshots]
    )
    report = build_backtest_report(result, benchmark_result=benchmark)
    assert report.performance.cumulative_return == pytest.approx(
        report.benchmark.performance.cumulative_return
    )


def test_baseline_runner_is_deterministic_serializable_and_end_to_end() -> None:
    days = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
    store = MemoryMarketStore({"SPY": frame("SPY", days, [(100, 100)] * 3)})
    calendar = XNYSTradingCalendar()
    strategy = SpyBuyAndHoldStrategy(store, calendar)
    subject = engine(store)
    first = run_baseline_strategy(
        strategy, start=days[0], end=days[-1], engine=subject,
        market_store=store, calendar=calendar,
    )
    second = run_baseline_strategy(
        strategy, start=days[0], end=days[-1], engine=subject,
        market_store=store, calendar=calendar,
    )
    assert first == second
    assert first["status"] == "completed"
    assert first["metrics"]["warnings"]
    assert json.loads(json.dumps(first))["run_id"] == first["run_id"]


def test_comparison_contains_three_completed_strategies_without_winner() -> None:
    names = ["spy_buy_hold", "equal_weight", "momentum_20d_top10"]
    reports = []
    for name in names:
        reports.append({
            "strategy_name": name, "strategy_version": f"{name}-v1",
            "status": "completed", "run_id": name,
            "metrics": {
                "performance": {
                    "cumulative_return": 0, "cagr": 0, "sharpe_ratio": None,
                    "sortino_ratio": None, "max_drawdown": 0,
                    "annualized_volatility": 0,
                },
                "costs": {"total_turnover": 0, "total_transaction_cost": 0},
                "exposure": {"average_cash_weight": 0},
            },
        })
    comparison = build_baseline_comparison(reports)
    assert set(comparison["strategies"]) == set(names)
    assert "winner" not in comparison


def test_corporate_action_failure_is_not_reported_as_completed() -> None:
    days = [date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)]
    events = pd.DataFrame([{
        "event_id": "evt-1", "ticker": "SPY", "event_date": days[2],
        "event_type": "complex_distribution", "training_exclusion": True,
        "adjustment_supported": False,
    }])
    store = MemoryMarketStore(
        {"SPY": frame("SPY", days, [(100, 100)] * 3)}, events=events,
    )
    calendar = XNYSTradingCalendar()
    report = run_baseline_strategy(
        SpyBuyAndHoldStrategy(store, calendar), start=days[0], end=days[-1],
        engine=engine(store), market_store=store, calendar=calendar,
    )
    assert report["status"] == "failed"
    assert report["ticker"] == "SPY"
    assert report["event_date"] == days[2].isoformat()
    assert report["event_id"] == "evt-1"
    assert report["reason"] == "complex_distribution"
    assert "metrics" not in report
