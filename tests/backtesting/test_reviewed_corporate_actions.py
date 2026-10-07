from __future__ import annotations

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from investment_system.backtesting import (
    BacktestConfig, BacktestDataError, CashFlowType, CostBasisStatus,
    HistoricalBacktestEngine, OrderSide, PortfolioLedger, SimulatedFill,
    TargetAllocation,
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
GOOGLE_EVENT = "9aef821b433135154689"


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
            (date(2012, 9, 24), 42, 42),
            (date(2012, 9, 25), 42, 42),
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


def test_purchase_after_mdlz_entitlement_close_does_not_receive_distribution() -> None:
    subject = engine(mdlz_store(), cash=300)
    decision = date(2012, 10, 1)
    result = subject.run(
        decision,
        date(2012, 10, 2),
        {decision: allocation(subject, decision, MDLZ=1)},
    )
    assert result.corporate_action_transformations == []
    assert "KRFT" not in {item.ticker for item in result.snapshots[-1].positions}


def test_mdlz_regular_way_sale_after_record_date_reduces_entitlement() -> None:
    subject = engine(mdlz_store(), cash=300)
    entry, sale_decision = date(2012, 9, 18), date(2012, 9, 24)
    result = subject.run(
        entry,
        date(2012, 10, 2),
        {
            entry: allocation(subject, entry, MDLZ=1),
            sale_decision: allocation(subject, sale_decision, MDLZ=0.5),
        },
    )
    transformation = result.corporate_action_transformations[0]
    assert transformation.record_date == date(2012, 9, 19)
    assert transformation.entitlement_date == date(2012, 10, 1)
    assert transformation.quantity_before == 15
    assert transformation.distributed_quantity == 5


def test_mdlz_regular_way_purchase_after_record_date_acquires_entitlement() -> None:
    subject = engine(mdlz_store(), cash=1_260)
    decision = date(2012, 9, 24)
    result = subject.run(
        decision,
        date(2012, 10, 2),
        {decision: allocation(subject, decision, MDLZ=1)},
    )
    transformation = result.corporate_action_transformations[0]
    assert transformation.quantity_before == 30
    assert transformation.distributed_quantity == 10


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


def abt_store(*, include_abbv: bool = True) -> MemoryMarketStore:
    processing = date(2013, 1, 2)
    local_bars = {
        "ABT": bars("ABT", [
            (date(2012, 12, 11), 65, 65),
            (date(2012, 12, 12), 65, 65),
            (date(2012, 12, 27), 65, 65),
            (date(2012, 12, 28), 65, 65),
            (date(2012, 12, 31), 65, 65),
            (processing, 30, 30),
            (date(2013, 1, 3), 30, 30),
        ]),
    }
    if include_abbv:
        local_bars["ABBV"] = bars("ABBV", [
            (processing, 35, 35),
            (date(2013, 1, 3), 35, 35),
        ])
    return MemoryMarketStore(
        local_bars,
        {"ABT": pd.DataFrame([
            provider_action(
                "ABT", processing, "dividend", dividend=34.649721,
            ),
        ])},
        event(ABT_EVENT, "ABT", processing, "complex_distribution"),
    )


ABT_EVENT = "b35533b35976ca04e483"


def run_abt():
    subject = engine(abt_store(), cash=650)
    entry, processing = date(2012, 12, 11), date(2013, 1, 2)
    return subject.run(
        entry,
        date(2013, 1, 3),
        {
            entry: allocation(subject, entry, ABT=1),
            processing: allocation(subject, processing, ABT=6 / 13),
        },
    )


def test_abt_distributes_one_for_one_without_pseudo_dividend_double_count() -> None:
    result = run_abt()
    snapshot = next(
        item for item in result.snapshots if item.as_of.date() == date(2013, 1, 2)
    )
    positions = {item.ticker: item for item in snapshot.positions}
    assert positions["ABT"].quantity == 10
    assert positions["ABT"].average_cost == 65
    assert positions["ABBV"].quantity == 10
    assert positions["ABBV"].average_cost is None
    assert positions["ABBV"].cost_basis_status == CostBasisStatus.UNALLOCATED
    assert snapshot.nav == 650
    assert result.cash_flows == []
    transformation = result.corporate_action_transformations[0]
    assert transformation.event_id == ABT_EVENT
    assert transformation.processed_at == XNYSTradingCalendar().session_open(
        date(2013, 1, 2),
    )
    assert transformation.record_date == date(2012, 12, 12)
    assert transformation.entitlement_date == date(2012, 12, 31)
    assert transformation.quantity_before == 10
    assert transformation.quantity_after == 10
    assert transformation.distributed_security == "ABBV"
    assert transformation.distributed_quantity == 10


def test_abt_auxiliary_holding_is_liquidated_by_implicit_zero_target() -> None:
    result = run_abt()
    sale = next(
        fill for fill in result.fills
        if fill.ticker == "ABBV" and fill.side == OrderSide.SELL
    )
    assert sale.filled_at.date() == date(2013, 1, 3)
    assert "ABBV" not in {item.ticker for item in result.snapshots[-1].positions}
    assert build_backtest_report(result).total_trading_pnl is None


def test_abt_regular_way_purchase_after_record_date_acquires_entitlement() -> None:
    subject = engine(abt_store(), cash=650)
    decision = date(2012, 12, 27)
    result = subject.run(
        decision,
        date(2013, 1, 2),
        {decision: allocation(subject, decision, ABT=1)},
    )
    assert result.corporate_action_transformations[0].distributed_quantity == 10


def test_abt_regular_way_sale_after_record_date_reduces_entitlement() -> None:
    subject = engine(abt_store(), cash=650)
    entry, sale_decision = date(2012, 12, 11), date(2012, 12, 27)
    result = subject.run(
        entry,
        date(2013, 1, 2),
        {
            entry: allocation(subject, entry, ABT=1),
            sale_decision: allocation(subject, sale_decision, ABT=0.5),
        },
    )
    assert result.corporate_action_transformations[0].distributed_quantity == 5


def test_abt_fractional_entitlement_follows_backtest_share_policy() -> None:
    entry = date(2012, 12, 11)
    fractional_subject = engine(abt_store(), cash=682.5)
    fractional = fractional_subject.run(
        entry,
        date(2013, 1, 2),
        {entry: allocation(fractional_subject, entry, ABT=1)},
    )
    assert fractional.corporate_action_transformations[0].distributed_quantity == 10.5

    whole_subject = engine(abt_store(), cash=650, fractional=False)
    whole = whole_subject.run(
        entry,
        date(2013, 1, 2),
        {entry: allocation(whole_subject, entry, ABT=1)},
    )
    assert whole.corporate_action_transformations[0].distributed_quantity == 10


def test_abt_transformation_is_deterministic() -> None:
    assert (
        run_abt().corporate_action_transformations
        == run_abt().corporate_action_transformations
    )


def test_abt_missing_distributed_security_data_blocks() -> None:
    subject = engine(abt_store(include_abbv=False), cash=650)
    entry = date(2012, 12, 11)
    with pytest.raises(BacktestDataError, match="auxiliary-security raw open"):
        subject.run(
            entry,
            date(2013, 1, 2),
            {entry: allocation(subject, entry, ABT=1)},
        )


def test_existing_abbv_position_is_merged_and_can_receive_later_buys() -> None:
    ledger = PortfolioLedger(BacktestConfig(initial_cash=1_000))
    first = SimulatedFill(
        fill_id="first",
        order_id="order-first",
        allocation_id="allocation-first",
        ticker="ABBV",
        side=OrderSide.BUY,
        quantity=2,
        raw_open_price=35,
        fill_price=35,
        notional=70,
        filled_at=datetime(2012, 12, 31, 9, 30, tzinfo=NY),
    )
    ledger.apply_fill(first)
    ledger.add_unallocated_distribution("ABBV", 10, market_price=35)
    second = first.model_copy(update={
        "fill_id": "second",
        "order_id": "order-second",
        "quantity": 1,
        "notional": 35,
    })
    ledger.apply_fill(second)
    position = ledger.positions["ABBV"]
    assert position.quantity == 13
    assert position.average_cost is None
    assert position.cost_basis_status == CostBasisStatus.UNALLOCATED


def google_store(
    *, include_goog: bool = True, include_processing_parent: bool = True,
) -> MemoryMarketStore:
    processing = date(2014, 4, 3)
    parent_rows = [
        (date(2014, 3, 26), 1_000, 1_000),
        (date(2014, 3, 27), 1_000, 1_000),
        (date(2014, 4, 1), 1_000, 1_000),
        (date(2014, 4, 2), 1_000, 1_000),
        (date(2014, 4, 4), 500, 500),
    ]
    if include_processing_parent:
        parent_rows.insert(-1, (processing, 500, 500))
    local_bars = {"GOOGL": bars("GOOGL", parent_rows)}
    if include_goog:
        local_bars["GOOG"] = bars("GOOG", [
            (date(2014, 3, 27), 500, 500),
            (date(2014, 4, 1), 500, 500),
            (date(2014, 4, 2), 500, 500),
            (processing, 500, 500),
            (date(2014, 4, 4), 500, 500),
        ])
    return MemoryMarketStore(
        local_bars,
        {"GOOGL": pd.DataFrame([
            provider_action(
                "GOOGL", processing, "dividend", dividend=567.971668,
            ),
        ])},
        event(GOOGLE_EVENT, "GOOGL", processing, "complex_distribution"),
    )


def run_google():
    subject = engine(google_store(), cash=1_000)
    entry, processing = date(2014, 3, 26), date(2014, 4, 3)
    return subject.run(
        entry,
        date(2014, 4, 4),
        {
            entry: allocation(subject, entry, GOOGL=1),
            processing: allocation(subject, processing, GOOGL=0.5),
        },
    )


def test_google_distribution_preserves_distinct_parent_and_child_economics() -> None:
    result = run_google()
    snapshot = next(
        item for item in result.snapshots if item.as_of.date() == date(2014, 4, 3)
    )
    positions = {item.ticker: item for item in snapshot.positions}
    assert set(positions) == {"GOOG", "GOOGL"}
    assert positions["GOOGL"].quantity == 1
    assert positions["GOOGL"].average_cost == 1_000
    assert positions["GOOG"].quantity == 1
    assert positions["GOOG"].average_cost is None
    assert positions["GOOG"].cost_basis_status == CostBasisStatus.UNALLOCATED
    assert snapshot.nav == 1_000
    assert result.cash_flows == []
    transformation = result.corporate_action_transformations[0]
    assert transformation.event_id == GOOGLE_EVENT
    assert transformation.record_date == date(2014, 3, 27)
    assert transformation.entitlement_date == date(2014, 4, 2)
    assert transformation.quantity_before == 1
    assert transformation.quantity_after == 1
    assert transformation.distributed_security == "GOOG"
    assert transformation.distributed_quantity == 1


def test_google_received_holding_and_strategy_purchase_merge_without_duplicates() -> None:
    subject = engine(google_store(), cash=1_000)
    entry, processing = date(2014, 3, 26), date(2014, 4, 3)
    result = subject.run(
        entry,
        date(2014, 4, 4),
        {
            entry: allocation(subject, entry, GOOGL=1),
            processing: allocation(subject, processing, GOOGL=0.25, GOOG=0.75),
        },
    )
    goog_positions = [
        item for item in result.snapshots[-1].positions if item.ticker == "GOOG"
    ]
    assert len(goog_positions) == 1
    assert goog_positions[0].quantity == 1.5
    assert goog_positions[0].cost_basis_status == CostBasisStatus.UNALLOCATED


def test_google_regular_way_purchase_after_record_date_acquires_entitlement() -> None:
    subject = engine(google_store(), cash=1_000)
    decision = date(2014, 4, 1)
    result = subject.run(
        decision,
        date(2014, 4, 3),
        {decision: allocation(subject, decision, GOOGL=1)},
    )
    assert result.corporate_action_transformations[0].distributed_quantity == 1


def test_google_regular_way_sale_after_record_date_loses_entitlement() -> None:
    subject = engine(google_store(), cash=1_000)
    entry, sale_decision = date(2014, 3, 26), date(2014, 4, 1)
    result = subject.run(
        entry,
        date(2014, 4, 3),
        {
            entry: allocation(subject, entry, GOOGL=1),
            sale_decision: allocation(subject, sale_decision, GOOGL=0.5),
        },
    )
    assert result.corporate_action_transformations[0].distributed_quantity == 0.5


def test_google_missing_distributed_or_parent_raw_data_blocks() -> None:
    entry = date(2014, 3, 26)
    missing_goog = engine(google_store(include_goog=False), cash=1_000)
    with pytest.raises(BacktestDataError, match="auxiliary-security raw open"):
        missing_goog.run(
            entry,
            date(2014, 4, 3),
            {entry: allocation(missing_goog, entry, GOOGL=1)},
        )

    missing_googl = engine(
        google_store(include_processing_parent=False), cash=1_000,
    )
    with pytest.raises(BacktestDataError, match="parent-security raw open"):
        missing_googl.run(
            entry,
            date(2014, 4, 3),
            {entry: allocation(missing_googl, entry, GOOGL=1)},
        )


def test_google_transformation_is_deterministic() -> None:
    assert (
        run_google().corporate_action_transformations
        == run_google().corporate_action_transformations
    )


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


def test_distributed_abbv_can_later_be_selected_from_development_universe() -> None:
    day = date(2014, 1, 2)
    rows = pd.DataFrame([{
        "ticker": "ABBV",
        "decision_date": day,
        "decision_time": datetime(2014, 1, 2, 20, 15, tzinfo=NY),
        "model_eligible": True,
        "momentum_20d": 0.1,
    }])
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
        "tickers": ["ABBV"],
    })
    generated = EqualWeightStrategy(
        FeatureStore(rows), universe, XNYSTradingCalendar(),
    ).generate_allocations(day, day).allocations[day]
    assert generated.weights == {"ABBV": 1.0}


def test_goog_and_googl_are_independently_strategy_eligible() -> None:
    day = date(2015, 1, 2)
    base = {
        "decision_date": day,
        "decision_time": datetime(2015, 1, 2, 20, 15, tzinfo=NY),
        "momentum_20d": 0.1,
    }
    rows = pd.DataFrame([
        {**base, "ticker": "GOOG", "model_eligible": True},
        {**base, "ticker": "GOOGL", "model_eligible": True},
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
        "tickers": ["GOOG", "GOOGL"],
    })
    strategy = EqualWeightStrategy(
        FeatureStore(rows), universe, XNYSTradingCalendar(),
    )
    both = strategy.generate_allocations(day, day).allocations[day]
    assert both.weights == {"GOOG": 0.5, "GOOGL": 0.5}

    rows.loc[rows["ticker"] == "GOOG", "model_eligible"] = False
    only_class_a = EqualWeightStrategy(
        FeatureStore(rows), universe, XNYSTradingCalendar(),
    ).generate_allocations(day, day).allocations[day]
    assert only_class_a.weights == {"GOOGL": 1.0}
