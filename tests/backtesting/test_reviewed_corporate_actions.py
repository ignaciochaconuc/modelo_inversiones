from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from investment_system.backtesting import (
    BacktestConfig, BacktestDataError, CashFlowType, CostBasisStatus,
    HistoricalBacktestEngine, OrderSide, TargetAllocation,
    UnmodelledCorporateActionError, build_backtest_report,
    load_reviewed_corporate_action_treatments,
)
from investment_system.backtesting.corporate_actions import (
    ReviewedCorporateActionTreatments,
)
from investment_system.backtesting.strategies import EqualWeightStrategy
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.universe import UniverseConfig


NY = ZoneInfo("America/New_York")
MDLZ_EVENT = "89f2ab472a86d18abc22"
TMUS_EVENT = "e653f71b02957333e821"


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


class FeatureStore:
    def __init__(self, rows: pd.DataFrame) -> None:
        self.rows = rows

    def read_feature_range(
        self,
        start: date,
        end: date,
        *,
        columns: list[str],
        tickers: list[str] | None = None,
    ) -> pd.DataFrame:
        result = self.rows.copy()
        if tickers is not None:
            result = result[result["ticker"].isin(tickers)]
        return result[["ticker", "decision_date", *columns]].copy()


def bars(ticker: str, rows: list[tuple[date, float, float]]) -> pd.DataFrame:
    return pd.DataFrame([
        {
            "ticker": ticker,
            "trading_date": day,
            "open": open_,
            "close": close,
            "available_at": datetime(
                day.year, day.month, day.day, 20, tzinfo=NY,
            ),
        }
        for day, open_, close in rows
    ])


def provider_action(
    ticker: str,
    day: date,
    kind: str,
    *,
    split: float | None = None,
    dividend: float | None = None,
) -> dict[str, object]:
    return {
        "ticker": ticker,
        "effective_date": day,
        "action_type": kind,
        "split_factor": split,
        "dividend_cash": dividend,
    }


def event(event_id: str, ticker: str, day: date, event_type: str) -> pd.DataFrame:
    return pd.DataFrame([{
        "event_id": event_id,
        "ticker": ticker,
        "event_date": day,
        "event_type": event_type,
        "training_exclusion": True,
        "adjustment_supported": False,
    }])


def engine(
    store: MemoryMarketStore,
    *,
    cash: float,
    fractional: bool = True,
    registry: ReviewedCorporateActionTreatments | None = None,
) -> HistoricalBacktestEngine:
    return HistoricalBacktestEngine(
        BacktestConfig(
            initial_cash=cash,
            allow_fractional_shares=fractional,
        ),
        store,
        XNYSTradingCalendar(),
        reviewed_treatments=(
            registry or load_reviewed_corporate_action_treatments()
        ),
    )


def allocation(
    subject: HistoricalBacktestEngine, day: date, **weights: float,
) -> TargetAllocation:
    return TargetAllocation(
        generated_at=subject.decision_time(day),
        weights=weights,
        cash_weight=1 - sum(weights.values()),
    )


def mdlz_store(*, include_krft: bool = True) -> MemoryMarketStore:
    record = date(2012, 9, 19)
    processing, liquidation = date(2012, 10, 2), date(2012, 10, 3)
    local_bars = {
        "MDLZ": bars("MDLZ", [
            (date(2012, 9, 18), 10, 10),
            (record, 10, 42),
            (date(2012, 10, 1), 42, 42),
            (processing, 28, 28),
            (liquidation, 28, 28),
        ]),
    }
    if include_krft:
        local_bars["KRFT"] = bars("KRFT", [
            (processing, 42, 42),
            (liquidation, 42, 42),
        ])
    return MemoryMarketStore(
        local_bars,
        {"MDLZ": pd.DataFrame([
            provider_action("MDLZ", processing, "dividend", dividend=14.6985),
        ])},
        event(MDLZ_EVENT, "MDLZ", processing, "complex_distribution"),
    )


def run_mdlz(*, cash: float = 300, fractional: bool = True):
    subject = engine(mdlz_store(), cash=cash, fractional=fractional)
    decision = date(2012, 9, 18)
    processing = date(2012, 10, 2)
    return subject.run(
        decision,
        date(2012, 10, 3),
        {
            decision: allocation(subject, decision, MDLZ=1),
            processing: allocation(subject, processing, MDLZ=2 / 3),
        },
    )


def test_mdlz_distributes_auxiliary_shares_preserves_parent_and_nav() -> None:
    result = run_mdlz()
    snapshot = next(
        item for item in result.snapshots if item.as_of.date() == date(2012, 10, 2)
    )
    positions = {item.ticker: item for item in snapshot.positions}
    assert positions["MDLZ"].quantity == 30
    assert positions["KRFT"].quantity == 10
    assert positions["KRFT"].average_cost is None
    assert positions["KRFT"].cost_basis_status == CostBasisStatus.UNALLOCATED
    assert snapshot.nav == pytest.approx(30 * 28 + 10 * 42)
    prior = next(
        item for item in result.snapshots if item.as_of.date() == date(2012, 10, 1)
    )
    assert snapshot.nav == prior.nav
    assert not any(flow.cash_flow_type == CashFlowType.DIVIDEND for flow in result.cash_flows)


def test_mdlz_auxiliary_position_is_implicitly_liquidated_at_next_open() -> None:
    result = run_mdlz()
    krft_sales = [
        fill for fill in result.fills
        if fill.ticker == "KRFT" and fill.side == OrderSide.SELL
    ]
    assert len(krft_sales) == 1
    assert krft_sales[0].filled_at.date() == date(2012, 10, 3)
    assert "KRFT" not in {item.ticker for item in result.snapshots[-1].positions}
    assert result.pnl_incomplete_tickers == ["KRFT"]
    report = build_backtest_report(result)
    assert report.trading_pnl_complete is False
    assert report.total_trading_pnl is None
    assert report.performance.final_nav == pytest.approx(result.snapshots[-1].nav)


def test_mdlz_transformation_is_event_linked_and_deterministic() -> None:
    first, second = run_mdlz(), run_mdlz()
    assert first.corporate_action_transformations == second.corporate_action_transformations
    transformation = first.corporate_action_transformations[0]
    assert transformation.event_id == MDLZ_EVENT
    assert transformation.quantity_before == 30
    assert transformation.quantity_after == 30
    assert transformation.distributed_security == "KRFT"
    assert transformation.distributed_quantity == 10


def test_mdlz_fractional_policy_keeps_fractions_or_blocks_without_actual_price() -> None:
    fractional = run_mdlz(cash=315)
    snapshot = next(
        item for item in fractional.snapshots
        if item.as_of.date() == date(2012, 10, 2)
    )
    assert next(item for item in snapshot.positions if item.ticker == "KRFT").quantity == 10.5
    with pytest.raises(UnmodelledCorporateActionError, match="fractional cash-in-lieu"):
        run_mdlz(cash=310, fractional=False)
    whole = run_mdlz(cash=300, fractional=False)
    assert whole.corporate_action_transformations[0].distributed_quantity == 10


def test_mdlz_missing_auxiliary_market_data_blocks_simulation() -> None:
    subject = engine(mdlz_store(include_krft=False), cash=300)
    decision = date(2012, 9, 18)
    with pytest.raises(BacktestDataError, match="auxiliary-security raw open"):
        subject.run(
            decision,
            date(2012, 10, 2),
            {decision: allocation(subject, decision, MDLZ=1)},
        )


def test_post_record_date_purchase_does_not_receive_mdlz_distribution() -> None:
    subject = engine(mdlz_store(), cash=300)
    decision = date(2012, 10, 1)
    result = subject.run(
        decision,
        date(2012, 10, 2),
        {decision: allocation(subject, decision, MDLZ=1)},
    )
    assert result.corporate_action_transformations == []
    assert "KRFT" not in {item.ticker for item in result.snapshots[-1].positions}


def tmus_store() -> MemoryMarketStore:
    effective, processing = date(2013, 4, 30), date(2013, 5, 1)
    return MemoryMarketStore(
        {"TMUS": bars("TMUS", [
            (date(2013, 4, 29), 10, 10),
            (effective, 10, 11.84),
            (processing, 15.5818, 15.5818),
        ])},
        {"TMUS": pd.DataFrame([
            provider_action("TMUS", processing, "split", split=0.5),
            provider_action("TMUS", processing, "dividend", dividend=8.1),
        ])},
        event(TMUS_EVENT, "TMUS", processing, "complex_recapitalization"),
    )


def run_tmus():
    subject = engine(tmus_store(), cash=100)
    decision = date(2013, 4, 29)
    return subject.run(
        decision,
        date(2013, 5, 1),
        {decision: allocation(subject, decision, TMUS=1)},
    )


def test_tmus_applies_exact_cash_and_split_without_double_counting() -> None:
    result = run_tmus()
    position = result.snapshots[-1].positions[0]
    assert position.quantity == 5
    assert position.average_cost == 20
    assert result.snapshots[-1].cash == pytest.approx(40.491)
    assert result.snapshots[-1].nav == pytest.approx(118.4)
    assert len(result.cash_flows) == 1
    flow = result.cash_flows[0]
    assert flow.cash_flow_type == CashFlowType.RECAPITALIZATION_CASH
    assert flow.event_id == TMUS_EVENT
    assert flow.amount_per_share == 4.0491
    assert flow.amount == pytest.approx(40.491)
    assert result.realized_pnl == 0
    assert result.corporate_action_transformations[0].event_id == TMUS_EVENT


def test_tmus_result_and_transformation_are_deterministic() -> None:
    assert run_tmus().model_dump() == run_tmus().model_dump()


def test_unknown_complex_event_still_blocks_with_reviewed_registry_present() -> None:
    d1, d2, event_day = date(2025, 1, 2), date(2025, 1, 3), date(2025, 1, 6)
    store = MemoryMarketStore(
        {"AAPL": bars("AAPL", [(d1, 10, 10), (d2, 10, 10), (event_day, 10, 10)])},
        events=event("unknown-event", "AAPL", event_day, "merger"),
    )
    subject = engine(store, cash=100)
    with pytest.raises(UnmodelledCorporateActionError) as error:
        subject.run(d1, event_day, {d1: allocation(subject, d1, AAPL=1)})
    assert error.value.event_id == "unknown-event"


def test_auxiliary_security_does_not_enter_strategy_universe() -> None:
    day = date(2025, 1, 2)
    rows = pd.DataFrame([
        {
            "ticker": ticker,
            "decision_date": day,
            "decision_time": datetime(2025, 1, 2, 20, 15, tzinfo=NY),
            "model_eligible": True,
            "momentum_20d": 1.0,
        }
        for ticker in ("MDLZ", "KRFT")
    ])
    universe = UniverseConfig.model_validate({
        "benchmark": "SPY",
        "asset_class": "US_EQUITY",
        "universe_type": "development_fixed",
        "description": "test",
        "universe": {
            "name": "test",
            "point_in_time": False,
            "survivorship_bias_warning": True,
            "as_of": "2026-10-05",
        },
        "tickers": ["MDLZ"],
    })
    strategy = EqualWeightStrategy(
        FeatureStore(rows), universe, XNYSTradingCalendar(),
    )
    generated = strategy.generate_allocations(day, day).allocations[day]
    assert generated.weights == {"MDLZ": 1.0}
    assert "KRFT" not in universe.tickers
