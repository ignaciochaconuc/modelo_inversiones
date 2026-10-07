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

from investment_system.backtesting.portfolio import PortfolioLedger
from investment_system.backtesting.schemas import (
    BacktestConfig, BacktestResult, CashFlowType, CorporateActionCashFlow,
    OrderExecutionRecord, OrderSide, OrderStatus, PortfolioSnapshot,
    SimulatedFill, SimulatedOrder, TargetAllocation, VALUE_TOLERANCE,
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
    ) -> None:
        self.config = config
        self.market_store = market_store
        self.calendar = calendar
        self.timezone = ZoneInfo(market_timezone)
        self.decision_cutoff = time.fromisoformat(decision_cutoff)

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
        tickers = sorted({ticker for allocation in allocations.values() for ticker in allocation.weights})
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
        return _stable_id("run", start, end, self.config.model_dump(mode="json"), payload)

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
    ) -> list[_PendingOrder]:
        held = set(ledger.positions)
        for event in complex_events:
            if (
                event.ticker in held
                and bool(event.training_exclusion)
                and not bool(event.adjustment_supported)
            ):
                raise UnmodelledCorporateActionError(
                    event.ticker, session, str(event.event_id), str(event.event_type),
                )

        adjusted_pending = pending
        for ticker in sorted(set(actions) | held):
            day_actions = actions.get(ticker, {}).get(session, [])
            split_factors = [
                float(action.split_factor)
                for action in day_actions
                if str(action.action_type).lower().endswith("split")
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
        return adjusted_pending

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
    ) -> dict[str, float]:
        """Capture post-split, pre-open quantities entitled on Tiingo ex-date."""
        entitlements: dict[str, float] = {}
        positions = ledger.positions
        for ticker in sorted(actions):
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
    ) -> None:
        for ticker in sorted(actions):
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
        snapshots: list[PortfolioSnapshot] = []

        for session in sessions:
            pending = self._apply_pre_open_actions(
                session, ledger, pending_by_date.pop(session, []), bars, actions,
                complex_by_date.get(session, []), cash_flows,
            )
            dividend_entitlements = self._capture_dividend_entitlements(
                session, ledger, actions,
            )
            self._execute_pending(session, ledger, pending, bars, fills, executions)
            prices, stale = self._valuation_prices(session, ledger, bars)
            self._apply_dividends(
                session, ledger, actions, dividend_entitlements, cash_flows,
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
            cash_flows=cash_flows, realized_pnl=ledger.realized_pnl,
            final_unrealized_pnl=snapshots[-1].unrealized_pnl,
            metadata={
                "start": start.isoformat(), "end": end.isoformat(),
                "market_timezone": str(self.timezone),
                "decision_cutoff": self.decision_cutoff.isoformat(timespec="minutes"),
                "execution_timing": "next_session_raw_open",
                "valuation_timing": "raw_close_then_dividend",
                "universe_point_in_time": False,
                "survivorship_bias_warning": True,
            },
        )
