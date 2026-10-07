"""Generic point-in-time historical loop; strategy logic deliberately lives elsewhere."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime, time
import hashlib
import json
import math
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from investment_system.backtesting.corporate_actions import (
    EntitlementTiming, ProviderActionType,
    RecapitalizationCashAndSplitTreatment,
    ReviewedCorporateActionTreatments, ReviewedTreatment,
    SpinOffDistributionTreatment,
)
from investment_system.backtesting.portfolio import PortfolioLedger
from investment_system.backtesting.schemas import (
    BacktestConfig, BacktestResult, CashFlowType, CorporateActionCashFlow,
    CorporateActionTransformation, CostBasisStatus, OrderExecutionRecord,
    OrderSide, OrderStatus, PortfolioSnapshot, SimulatedFill, SimulatedOrder,
    TargetAllocation, VALUE_TOLERANCE,
)
from investment_system.data.calendar import TradingCalendar
from investment_system.data.storage.market_store import MarketDataStore


class BacktestDataError(ValueError):
    """Required raw market data is absent or temporally invalid."""


class UnmodelledCorporateActionError(BacktestDataError):
    """A held position crossed a complex action with no supported adjustment."""

    def __init__(self, ticker: str, event_date: date, event_id: str, reason: str) -> None:
        self.ticker = ticker
        self.event_date = event_date
        self.event_id = event_id
        self.reason = reason
        super().__init__(
            f"unmodelled corporate action for {ticker} on {event_date}: "
            f"event_id={event_id} reason={reason}"
        )


class BaseBacktestEngine(ABC):
    """Contract enforcing decisions after close and fills at next session open."""

    @abstractmethod
    def run(
        self, start: date, end: date,
        allocations: Mapping[date, TargetAllocation],
        *, run_id: str | None = None,
    ) -> BacktestResult: ...


@dataclass(frozen=True)
class _PendingOrder:
    order: SimulatedOrder
    effective_quantity: float


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:20]
    return f"{prefix}_{digest}"


class HistoricalBacktestEngine(BaseBacktestEngine):
    """Session engine using raw opens/closes and explicit corporate actions."""

    def __init__(
        self,
        config: BacktestConfig,
        market_store: MarketDataStore,
        calendar: TradingCalendar,
        *,
        market_timezone: str = "America/New_York",
        decision_cutoff: str = "20:15",
        reviewed_treatments: ReviewedCorporateActionTreatments | None = None,
    ) -> None:
        self.config = config
        self.market_store = market_store
        self.calendar = calendar
        self.timezone = ZoneInfo(market_timezone)
        self.decision_cutoff = time.fromisoformat(decision_cutoff)
        self.reviewed_treatments = reviewed_treatments or ReviewedCorporateActionTreatments(
            schema_version="1",
        )

    def decision_time(self, session: date) -> datetime:
        return datetime.combine(session, self.decision_cutoff, self.timezone)

    def _sessions(self, start: date, end: date) -> list[date]:
        if start > end:
            raise ValueError("start must be <= end")
        return [
            date.fromordinal(value)
            for value in range(start.toordinal(), end.toordinal() + 1)
            if self.calendar.is_session(date.fromordinal(value))
        ]

    @staticmethod
    def _rows_by_date(frame: pd.DataFrame, column: str) -> dict[date, list[Any]]:
        if frame.empty:
            return {}
        result: dict[date, list[Any]] = {}
        for row in frame.itertuples(index=False):
            result.setdefault(pd.Timestamp(getattr(row, column)).date(), []).append(row)
        return result

    def _load_inputs(
        self, allocations: Mapping[date, TargetAllocation],
    ) -> tuple[dict[str, dict[date, Any]], dict[str, dict[date, list[Any]]], dict[date, list[Any]]]:
        tickers = sorted(
            {ticker for allocation in allocations.values() for ticker in allocation.weights}
            | self.reviewed_treatments.auxiliary_tickers()
        )
        bars: dict[str, dict[date, Any]] = {}
        actions: dict[str, dict[date, list[Any]]] = {}
        for ticker in tickers:
            raw = self.market_store.read_bars(ticker)
            bars[ticker] = {
                day: rows[-1]
                for day, rows in self._rows_by_date(raw, "trading_date").items()
            }
            actions[ticker] = self._rows_by_date(
                self.market_store.read_actions(ticker), "effective_date",
            )
        events = self._rows_by_date(
            self.market_store.read_corporate_action_events(), "event_date",
        )
        return bars, actions, events

    def _validate_allocations(
        self, start: date, end: date, allocations: Mapping[date, TargetAllocation],
    ) -> None:
        for decision_date, allocation in allocations.items():
            if not self.calendar.is_session(decision_date):
                raise ValueError(f"allocation date is not an XNYS session: {decision_date}")
            if not start <= decision_date <= end:
                raise ValueError(f"allocation date is outside the backtest range: {decision_date}")
            if allocation.generated_at != self.decision_time(decision_date):
                raise ValueError(
                    f"allocation generated_at must equal decision_time for {decision_date}"
                )

    def _run_id(
        self, start: date, end: date, allocations: Mapping[date, TargetAllocation],
    ) -> str:
        payload = [
            {
                "date": day.isoformat(),
                "generated_at": allocation.generated_at.isoformat(),
                "weights": sorted(allocation.weights.items()),
                "cash_weight": allocation.cash_weight,
                "risk_decision_id": allocation.risk_decision_id,
            }
            for day, allocation in sorted(allocations.items())
        ]
        return _stable_id(
            "run",
            start,
            end,
            self.config.model_dump(mode="json"),
            self.reviewed_treatments.model_dump(mode="json"),
            payload,
        )

    @staticmethod
    def _raw_price(row: Any | None, field: str) -> float | None:
        if row is None:
            return None
        value = getattr(row, field, None)
        if value is None or pd.isna(value):
            return None
        price = float(value)
        return price if math.isfinite(price) and price > 0 else None

    def _available_by_decision(self, row: Any | None, session: date) -> bool:
        if row is None:
            return False
        available_at = pd.to_datetime(
            getattr(row, "available_at", None), utc=True, errors="coerce",
        )
        cutoff = pd.Timestamp(self.decision_time(session)).tz_convert("UTC")
        return not pd.isna(available_at) and available_at <= cutoff

    def _apply_pre_open_actions(
        self,
        session: date,
        ledger: PortfolioLedger,
        pending: list[_PendingOrder],
        bars: dict[str, dict[date, Any]],
        actions: dict[str, dict[date, list[Any]]],
        complex_events: list[Any],
        cash_flows: list[CorporateActionCashFlow],
        transformations: list[CorporateActionTransformation],
        reviewed_entitlements: dict[str, float],
    ) -> tuple[list[_PendingOrder], set[tuple[str, ProviderActionType]]]:
        held = set(ledger.positions)
        adjusted_pending = pending
        consumed: set[tuple[str, ProviderActionType]] = set()
        for event in sorted(complex_events, key=lambda item: str(item.event_id)):
            event_id = str(event.event_id)
            treatment = self.reviewed_treatments.get(event_id)
            entitlement = reviewed_entitlements.get(event_id, 0.0)
            affected = event.ticker in held or entitlement > VALUE_TOLERANCE
            if not affected:
                continue
            if treatment is None:
                if not bool(event.training_exclusion) or bool(event.adjustment_supported):
                    continue
                raise UnmodelledCorporateActionError(
                    event.ticker, session, event_id, str(event.event_type),
                )
            self._validate_reviewed_treatment(event, treatment, session)
            adjusted_pending = self._apply_reviewed_treatment(
                event,
                treatment,
                entitlement,
                session,
                ledger,
                adjusted_pending,
                bars,
                cash_flows,
                transformations,
            )
            consumed.update(
                (treatment.ticker, action_type)
                for action_type in treatment.provider_action_types_consumed
            )

        for ticker in sorted(set(actions) | held):
            day_actions = actions.get(ticker, {}).get(session, [])
            split_factors = [
                float(action.split_factor)
                for action in day_actions
                if str(action.action_type).lower().endswith("split")
                and (ticker, ProviderActionType.SPLIT) not in consumed
            ]
            for sequence, factor in enumerate(split_factors):
                before = ledger.positions.get(ticker)
                cash_in_lieu_price = None
                fractional_quantity = 0.0
                if before is not None and not self.config.allow_fractional_shares:
                    exact = before.quantity * factor
                    fractional_quantity = exact - math.floor(exact + VALUE_TOLERANCE)
                    if fractional_quantity > VALUE_TOLERANCE:
                        cash_in_lieu_price = self._raw_price(
                            bars.get(ticker, {}).get(session), "open",
                        )
                        if cash_in_lieu_price is None:
                            raise BacktestDataError(
                                f"missing_execution_open for cash-in-lieu: {ticker} {session}"
                            )
                credited = ledger.apply_split(
                    ticker, factor, cash_in_lieu_price=cash_in_lieu_price,
                )
                if credited > VALUE_TOLERANCE:
                    cash_flows.append(CorporateActionCashFlow(
                        cash_flow_id=_stable_id(
                            "cashflow", "cash_in_lieu", ticker, session, sequence,
                        ),
                        ticker=ticker, cash_flow_type=CashFlowType.CASH_IN_LIEU,
                        effective_date=session, quantity=fractional_quantity,
                        amount_per_share=float(cash_in_lieu_price), amount=credited,
                        occurred_at=self.calendar.session_open(session),
                        notes="fractional split settlement at raw open proxy",
                    ))
                adjusted_pending = [
                    _PendingOrder(item.order, item.effective_quantity * factor)
                    if item.order.ticker == ticker else item
                    for item in adjusted_pending
                ]
        return adjusted_pending, consumed

    @staticmethod
    def _validate_reviewed_treatment(
        event: Any, treatment: ReviewedTreatment, session: date,
    ) -> None:
        if treatment.processing_date != session:
            raise BacktestDataError(
                f"reviewed treatment processing_date mismatch for {treatment.event_id}"
            )
        if treatment.ticker != str(event.ticker).upper():
            raise BacktestDataError(
                f"reviewed treatment ticker mismatch for {treatment.event_id}"
            )
        if treatment.event_type != str(event.event_type):
            raise BacktestDataError(
                f"reviewed treatment event_type mismatch for {treatment.event_id}"
            )

    def _apply_reviewed_treatment(
        self,
        event: Any,
        treatment: ReviewedTreatment,
        entitlement_quantity: float,
        session: date,
        ledger: PortfolioLedger,
        pending: list[_PendingOrder],
        bars: dict[str, dict[date, Any]],
        cash_flows: list[CorporateActionCashFlow],
        transformations: list[CorporateActionTransformation],
    ) -> list[_PendingOrder]:
        """Transform actual holdings/cash; raw historical prices remain untouched."""
        processed_at = self.calendar.session_open(session)
        if entitlement_quantity <= VALUE_TOLERANCE:
            return pending

        if isinstance(treatment, SpinOffDistributionTreatment):
            parent_open = self._raw_price(
                bars.get(treatment.ticker, {}).get(session), "open",
            )
            if parent_open is None:
                raise BacktestDataError(
                    "missing required parent-security raw open for "
                    f"{treatment.ticker} on {session}"
                )
            distributed_quantity = (
                entitlement_quantity * treatment.shares_per_parent_share
            )
            if not self.config.allow_fractional_shares and not math.isclose(
                distributed_quantity,
                round(distributed_quantity),
                abs_tol=VALUE_TOLERANCE,
            ):
                raise UnmodelledCorporateActionError(
                    treatment.ticker,
                    session,
                    treatment.event_id,
                    "reviewed spin-off has no actual fractional cash-in-lieu price",
                )
            if not self.config.allow_fractional_shares:
                distributed_quantity = float(round(distributed_quantity))
            initial_price = self._raw_price(
                bars.get(treatment.distributed_ticker, {}).get(session), "open",
            )
            if initial_price is None:
                raise BacktestDataError(
                    "missing required auxiliary-security raw open for "
                    f"{treatment.distributed_ticker} on {session}"
                )
            ledger.add_unallocated_distribution(
                treatment.distributed_ticker,
                distributed_quantity,
                market_price=initial_price,
            )
            parent = ledger.positions.get(treatment.ticker)
            transformation_id = _stable_id(
                "transformation",
                treatment.event_id,
                treatment.treatment_version,
                entitlement_quantity,
                distributed_quantity,
            )
            transformations.append(CorporateActionTransformation(
                transformation_id=transformation_id,
                event_id=treatment.event_id,
                ticker=treatment.ticker,
                event_type=treatment.event_type,
                record_date=treatment.record_date,
                entitlement_date=treatment.entitlement_date,
                effective_date=treatment.effective_date,
                processed_at=processed_at,
                treatment_type=treatment.treatment_type,
                treatment_version=treatment.treatment_version,
                quantity_before=entitlement_quantity,
                quantity_after=0.0 if parent is None else parent.quantity,
                distributed_security=treatment.distributed_ticker,
                distributed_quantity=distributed_quantity,
                cash_received=0.0,
                cost_basis_status=CostBasisStatus.UNALLOCATED,
                notes=treatment.review_notes,
            ))
            return pending

        if isinstance(treatment, RecapitalizationCashAndSplitTreatment):
            current = ledger.positions.get(treatment.ticker)
            if current is None or not math.isclose(
                current.quantity,
                entitlement_quantity,
                rel_tol=1e-12,
                abs_tol=VALUE_TOLERANCE,
            ):
                raise BacktestDataError(
                    f"held quantity changed after entitlement for {treatment.event_id}"
                )
            cash_received = ledger.apply_cash_distribution(
                entitlement_quantity,
                treatment.cash_per_pre_split_share,
            )
            cash_flows.append(CorporateActionCashFlow(
                cash_flow_id=_stable_id(
                    "cashflow", "recapitalization", treatment.event_id,
                    treatment.treatment_version,
                ),
                event_id=treatment.event_id,
                ticker=treatment.ticker,
                cash_flow_type=CashFlowType.RECAPITALIZATION_CASH,
                effective_date=treatment.effective_date,
                quantity=entitlement_quantity,
                amount_per_share=treatment.cash_per_pre_split_share,
                amount=cash_received,
                occurred_at=processed_at,
                notes=treatment.review_notes,
            ))
            cash_in_lieu_price = None
            fractional_quantity = 0.0
            if not self.config.allow_fractional_shares:
                exact = current.quantity * treatment.split_factor
                fractional_quantity = exact - math.floor(exact + VALUE_TOLERANCE)
                if fractional_quantity > VALUE_TOLERANCE:
                    cash_in_lieu_price = self._raw_price(
                        bars.get(treatment.ticker, {}).get(session), "open",
                    )
                    if cash_in_lieu_price is None:
                        raise BacktestDataError(
                            "missing_execution_open for recapitalization cash-in-lieu: "
                            f"{treatment.ticker} {session}"
                        )
            credited = ledger.apply_split(
                treatment.ticker,
                treatment.split_factor,
                cash_in_lieu_price=cash_in_lieu_price,
            )
            if credited > VALUE_TOLERANCE:
                cash_flows.append(CorporateActionCashFlow(
                    cash_flow_id=_stable_id(
                        "cashflow", "cash_in_lieu", treatment.event_id,
                        treatment.treatment_version,
                    ),
                    event_id=treatment.event_id,
                    ticker=treatment.ticker,
                    cash_flow_type=CashFlowType.CASH_IN_LIEU,
                    effective_date=treatment.effective_date,
                    quantity=fractional_quantity,
                    amount_per_share=float(cash_in_lieu_price),
                    amount=credited,
                    occurred_at=processed_at,
                    notes="fractional recapitalization settlement at raw open proxy",
                ))
            after = ledger.positions.get(treatment.ticker)
            transformations.append(CorporateActionTransformation(
                transformation_id=_stable_id(
                    "transformation",
                    treatment.event_id,
                    treatment.treatment_version,
                    entitlement_quantity,
                    cash_received,
                ),
                event_id=treatment.event_id,
                ticker=treatment.ticker,
                event_type=treatment.event_type,
                record_date=treatment.record_date,
                entitlement_date=treatment.entitlement_date,
                effective_date=treatment.effective_date,
                processed_at=processed_at,
                treatment_type=treatment.treatment_type,
                treatment_version=treatment.treatment_version,
                quantity_before=entitlement_quantity,
                quantity_after=0.0 if after is None else after.quantity,
                cash_received=cash_received,
                notes=treatment.review_notes,
            ))
            return [
                _PendingOrder(
                    item.order,
                    item.effective_quantity * treatment.split_factor,
                )
                if item.order.ticker == treatment.ticker else item
                for item in pending
            ]
        raise TypeError(f"unsupported reviewed treatment: {type(treatment).__name__}")

    def _capture_reviewed_entitlements(
        self,
        session: date,
        timing: EntitlementTiming,
        ledger: PortfolioLedger,
        entitlements: dict[str, float],
    ) -> None:
        positions = ledger.positions
        for treatment in self.reviewed_treatments.treatments_entitled_on(
            session, timing,
        ):
            position = positions.get(treatment.ticker)
            entitlements[treatment.event_id] = (
                0.0 if position is None else position.quantity
            )

    def _execute_pending(
        self,
        session: date,
        ledger: PortfolioLedger,
        pending: list[_PendingOrder],
        bars: dict[str, dict[date, Any]],
        fills: list[SimulatedFill],
        executions: list[OrderExecutionRecord],
    ) -> None:
        ordered = sorted(
            pending,
            key=lambda item: (
                0 if item.order.side == OrderSide.SELL else 1,
                item.order.ticker,
            ),
        )
        commission_rate = self.config.commission_bps / 10_000
        slippage_rate = self.config.slippage_bps / 10_000
        fill_time = self.calendar.session_open(session)
        for item in ordered:
            order = item.order
            requested = item.effective_quantity
            if order.execution_date != session:
                raise ValueError("pending order reached a session other than its execution_date")
            raw_open = self._raw_price(bars.get(order.ticker, {}).get(session), "open")
            if raw_open is None:
                executions.append(OrderExecutionRecord(
                    order_id=order.order_id, allocation_id=order.allocation_id,
                    ticker=order.ticker, execution_date=session,
                    status=OrderStatus.UNFILLED, requested_quantity=requested,
                    reason="missing_execution_open", recorded_at=fill_time,
                ))
                continue
            multiplier = 1 + slippage_rate if order.side == OrderSide.BUY else 1 - slippage_rate
            fill_price = raw_open * multiplier
            quantity = requested
            reason = None
            if order.side == OrderSide.BUY:
                maximum = ledger.cash / (fill_price * (1 + commission_rate))
                quantity = min(quantity, maximum)
                cash_reduced = quantity < requested - VALUE_TOLERANCE
                if not self.config.allow_fractional_shares:
                    quantity = float(math.floor(quantity + VALUE_TOLERANCE))
                if quantity < requested - VALUE_TOLERANCE:
                    reason = (
                        "reduced_to_available_cash"
                        if cash_reduced else "reduced_to_whole_shares"
                    )
            else:
                held = ledger.positions.get(order.ticker)
                quantity = min(quantity, held.quantity if held else 0.0)
                if not self.config.allow_fractional_shares:
                    quantity = float(math.floor(quantity + VALUE_TOLERANCE))
                if quantity < requested - VALUE_TOLERANCE:
                    reason = "reduced_to_available_position_or_whole_shares"
            if quantity <= VALUE_TOLERANCE:
                executions.append(OrderExecutionRecord(
                    order_id=order.order_id, allocation_id=order.allocation_id,
                    ticker=order.ticker, execution_date=session,
                    status=OrderStatus.UNFILLED, requested_quantity=requested,
                    reason=reason or "insufficient_position",
                    quantity_reduced=reason is not None, recorded_at=fill_time,
                ))
                continue
            notional = quantity * fill_price
            commission = notional * commission_rate
            fill = SimulatedFill(
                fill_id=_stable_id("fill", order.order_id, session, quantity, fill_price),
                order_id=order.order_id, allocation_id=order.allocation_id,
                ticker=order.ticker, side=order.side, quantity=quantity,
                raw_open_price=raw_open, fill_price=fill_price, notional=notional,
                commission=commission,
                slippage_cost=abs(fill_price - raw_open) * quantity,
                filled_at=fill_time,
            )
            ledger.apply_fill(fill)
            fills.append(fill)
            partial = quantity < requested - VALUE_TOLERANCE
            executions.append(OrderExecutionRecord(
                order_id=order.order_id, allocation_id=order.allocation_id,
                ticker=order.ticker, execution_date=session,
                status=OrderStatus.PARTIALLY_FILLED if partial else OrderStatus.FILLED,
                requested_quantity=requested, filled_quantity=quantity,
                reason=reason, quantity_reduced=partial, recorded_at=fill_time,
            ))

    def _valuation_prices(
        self, session: date, ledger: PortfolioLedger,
        bars: dict[str, dict[date, Any]],
    ) -> tuple[dict[str, float], list[str]]:
        prices: dict[str, float] = {}
        stale: list[str] = []
        for ticker, position in ledger.positions.items():
            row = bars.get(ticker, {}).get(session)
            close = (
                self._raw_price(row, "close")
                if self._available_by_decision(row, session)
                else None
            )
            if close is None:
                if position.market_price <= 0 or not math.isfinite(position.market_price):
                    raise BacktestDataError(
                        f"no prior valid valuation price for held ticker {ticker} on {session}"
                    )
                close = position.market_price
                stale.append(ticker)
            prices[ticker] = close
        return prices, stale

    @staticmethod
    def _capture_dividend_entitlements(
        session: date,
        ledger: PortfolioLedger,
        actions: dict[str, dict[date, list[Any]]],
        consumed: set[tuple[str, ProviderActionType]],
    ) -> dict[str, float]:
        """Capture post-split, pre-open quantities entitled on Tiingo ex-date."""
        entitlements: dict[str, float] = {}
        positions = ledger.positions
        for ticker in sorted(actions):
            if (ticker, ProviderActionType.DIVIDEND) in consumed:
                continue
            if any(
                str(action.action_type).lower().endswith("dividend")
                for action in actions[ticker].get(session, [])
            ):
                position = positions.get(ticker)
                entitlements[ticker] = position.quantity if position else 0.0
        return entitlements

    def _apply_dividends(
        self,
        session: date,
        ledger: PortfolioLedger,
        actions: dict[str, dict[date, list[Any]]],
        entitlements: dict[str, float],
        cash_flows: list[CorporateActionCashFlow],
        consumed: set[tuple[str, ProviderActionType]],
    ) -> None:
        for ticker in sorted(actions):
            if (ticker, ProviderActionType.DIVIDEND) in consumed:
                continue
            for sequence, action in enumerate(actions[ticker].get(session, [])):
                if not str(action.action_type).lower().endswith("dividend"):
                    continue
                quantity = entitlements.get(ticker, 0.0)
                per_share = float(action.dividend_cash)
                amount = ledger.apply_dividend(
                    ticker, per_share, entitlement_quantity=quantity,
                )
                if amount <= VALUE_TOLERANCE:
                    continue
                cash_flows.append(CorporateActionCashFlow(
                    cash_flow_id=_stable_id(
                        "cashflow", "dividend", ticker, session, sequence,
                    ),
                    ticker=ticker, cash_flow_type=CashFlowType.DIVIDEND,
                    effective_date=session, quantity=quantity,
                    amount_per_share=per_share, amount=amount,
                    occurred_at=self.calendar.session_close(session),
                    notes=(
                        "Tiingo ex-date entitlement; cash credited post-close "
                        "because payment date is unavailable"
                    ),
                ))

    def _orders_from_allocation(
        self,
        session: date,
        allocation: TargetAllocation,
        allocation_id: str,
        snapshot: PortfolioSnapshot,
        bars: dict[str, dict[date, Any]],
    ) -> list[SimulatedOrder]:
        current_values = {
            position.ticker: position.market_value for position in snapshot.positions
        }
        target_tickers = sorted(set(current_values) | set(allocation.weights))
        result: list[SimulatedOrder] = []
        execution_date = self.calendar.next_session(session)
        submitted_at = self.decision_time(session)
        for ticker in target_tickers:
            target_weight = allocation.weights.get(ticker, 0.0)
            delta = target_weight * snapshot.nav - current_values.get(ticker, 0.0)
            if abs(delta) <= VALUE_TOLERANCE:
                continue
            row = bars.get(ticker, {}).get(session)
            reference_price = self._raw_price(row, "close")
            if reference_price is None:
                raise BacktestDataError(
                    f"missing_decision_close for {ticker} on {session}"
                )
            if not self._available_by_decision(row, session):
                raise BacktestDataError(
                    f"decision close unavailable by decision_time for {ticker} on {session}"
                )
            quantity = abs(delta) / reference_price
            if not self.config.allow_fractional_shares:
                quantity = float(math.floor(quantity + VALUE_TOLERANCE))
            if quantity <= VALUE_TOLERANCE:
                continue
            side = OrderSide.BUY if delta > 0 else OrderSide.SELL
            sequence = len(result)
            result.append(SimulatedOrder(
                order_id=_stable_id("order", allocation_id, ticker, side, sequence),
                allocation_id=allocation_id,
                risk_decision_id=allocation.risk_decision_id,
                ticker=ticker, side=side, quantity=quantity,
                submitted_at=submitted_at, execution_date=execution_date,
                target_weight=target_weight, reference_price=reference_price,
            ))
        return result

    def run(
        self,
        start: date,
        end: date,
        allocations: Mapping[date, TargetAllocation],
        *,
        run_id: str | None = None,
    ) -> BacktestResult:
        sessions = self._sessions(start, end)
        if not sessions:
            raise ValueError("backtest range contains no trading sessions")
        self._validate_allocations(start, end, allocations)
        effective_run_id = run_id or self._run_id(start, end, allocations)
        if not effective_run_id.strip():
            raise ValueError("run_id must not be empty")
        bars, actions, complex_by_date = self._load_inputs(allocations)
        ledger = PortfolioLedger(self.config)
        pending_by_date: dict[date, list[_PendingOrder]] = {}
        result_allocations: list[TargetAllocation] = []
        orders: list[SimulatedOrder] = []
        fills: list[SimulatedFill] = []
        executions: list[OrderExecutionRecord] = []
        cash_flows: list[CorporateActionCashFlow] = []
        transformations: list[CorporateActionTransformation] = []
        reviewed_entitlements: dict[str, float] = {}
        snapshots: list[PortfolioSnapshot] = []

        for session in sessions:
            self._capture_reviewed_entitlements(
                session,
                EntitlementTiming.PRE_OPEN,
                ledger,
                reviewed_entitlements,
            )
            pending, consumed = self._apply_pre_open_actions(
                session, ledger, pending_by_date.pop(session, []), bars, actions,
                complex_by_date.get(session, []), cash_flows, transformations,
                reviewed_entitlements,
            )
            dividend_entitlements = self._capture_dividend_entitlements(
                session, ledger, actions, consumed,
            )
            self._execute_pending(session, ledger, pending, bars, fills, executions)
            self._capture_reviewed_entitlements(
                session,
                EntitlementTiming.POST_CLOSE,
                ledger,
                reviewed_entitlements,
            )
            prices, stale = self._valuation_prices(session, ledger, bars)
            self._apply_dividends(
                session, ledger, actions, dividend_entitlements, cash_flows,
                consumed,
            )
            snapshot = ledger.mark_to_market(
                prices, self.decision_time(session), stale_price_tickers=stale,
            )
            snapshots.append(snapshot)

            allocation = allocations.get(session)
            if allocation is None:
                continue
            allocation_id = _stable_id(
                "allocation", effective_run_id, session,
                sorted(allocation.weights.items()), allocation.cash_weight,
            )
            identified = allocation.model_copy(update={"allocation_id": allocation_id})
            result_allocations.append(identified)
            generated = self._orders_from_allocation(
                session, identified, allocation_id, snapshot, bars,
            )
            orders.extend(generated)
            for order in generated:
                pending_by_date.setdefault(order.execution_date, []).append(
                    _PendingOrder(order, order.quantity)
                )

        return BacktestResult(
            run_id=effective_run_id, config=self.config,
            allocations=result_allocations, snapshots=snapshots,
            orders=orders, fills=fills, executions=executions,
            cash_flows=cash_flows,
            corporate_action_transformations=transformations,
            realized_pnl=ledger.realized_pnl,
            final_unrealized_pnl=snapshots[-1].unrealized_pnl,
            pnl_incomplete_tickers=sorted(ledger.pnl_incomplete_tickers),
            metadata={
                "start": start.isoformat(), "end": end.isoformat(),
                "market_timezone": str(self.timezone),
                "decision_cutoff": self.decision_cutoff.isoformat(timespec="minutes"),
                "execution_timing": "next_session_raw_open",
                "valuation_timing": "raw_close_then_dividend",
                "universe_point_in_time": False,
                "survivorship_bias_warning": True,
                "reviewed_corporate_action_treatment_schema_version": (
                    self.reviewed_treatments.schema_version
                ),
            },
        )
