"""Deterministic long-only portfolio accounting for historical simulation."""
from __future__ import annotations

from datetime import datetime
import math

from investment_system.backtesting.schemas import (
    BacktestConfig, BacktestPosition, OrderSide, PortfolioSnapshot, SimulatedFill,
    VALUE_TOLERANCE,
)


class PortfolioLedger:
    """Maintain cash and unit positions without executing a backtest loop."""

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config
        self.initial_cash = config.initial_cash
        self.cash = config.initial_cash
        self._positions: dict[str, BacktestPosition] = {}
        self.realized_pnl = 0.0

    @property
    def positions(self) -> dict[str, BacktestPosition]:
        """Return a shallow copy so callers cannot replace internal holdings."""
        return dict(self._positions)

    def _validate_quantity(self, quantity: float) -> None:
        if quantity <= 0 or not math.isfinite(quantity):
            raise ValueError("quantity must be finite and positive")
        if not self.config.allow_fractional_shares and not math.isclose(quantity, round(quantity), abs_tol=VALUE_TOLERANCE):
            raise ValueError("fractional shares are disabled")

    def apply_fill(self, fill: SimulatedFill) -> None:
        """Apply one validated fill atomically to cash and holdings."""
        self._validate_quantity(fill.quantity)
        current = self._positions.get(fill.ticker)
        if fill.side == OrderSide.BUY:
            cash_required = fill.notional + fill.commission
            if cash_required > self.cash + VALUE_TOLERANCE:
                raise ValueError("insufficient cash for buy fill")
            old_quantity = current.quantity if current else 0.0
            old_cost = current.average_cost if current else 0.0
            new_quantity = old_quantity + fill.quantity
            average_cost = (old_quantity * old_cost + fill.notional) / new_quantity
            new_cash = self.cash - cash_required
            self._positions[fill.ticker] = BacktestPosition(
                ticker=fill.ticker, quantity=new_quantity, average_cost=average_cost,
                market_price=fill.fill_price,
            )
            self.cash = 0.0 if abs(new_cash) <= VALUE_TOLERANCE else new_cash
            return

        if current is None or fill.quantity > current.quantity + VALUE_TOLERANCE:
            raise ValueError("cannot sell more shares than the portfolio owns")
        remaining = current.quantity - fill.quantity
        new_cash = self.cash + fill.notional - fill.commission
        if new_cash < -VALUE_TOLERANCE:
            raise ValueError("sell commission would make cash negative")
        if remaining <= VALUE_TOLERANCE:
            del self._positions[fill.ticker]
        else:
            self._positions[fill.ticker] = BacktestPosition(
                ticker=current.ticker, quantity=remaining, average_cost=current.average_cost,
                market_price=fill.fill_price,
            )
        self.realized_pnl += (fill.fill_price - current.average_cost) * fill.quantity - fill.commission
        self.cash = 0.0 if abs(new_cash) <= VALUE_TOLERANCE else new_cash

    def apply_split(
        self, ticker: str, split_factor: float, *, cash_in_lieu_price: float | None = None,
    ) -> float:
        """Apply a split and return any deterministic fractional cash settlement."""
        if split_factor <= 0 or not math.isfinite(split_factor):
            raise ValueError("split_factor must be finite and positive")
        ticker = ticker.strip().upper()
        current = self._positions.get(ticker)
        if current is None:
            return 0.0
        exact_quantity = current.quantity * split_factor
        average_cost = current.average_cost / split_factor
        market_price = current.market_price / split_factor
        cash_credit = 0.0
        quantity = exact_quantity
        if not self.config.allow_fractional_shares:
            quantity = float(math.floor(exact_quantity + VALUE_TOLERANCE))
            fractional = exact_quantity - quantity
            if fractional > VALUE_TOLERANCE:
                if cash_in_lieu_price is None or cash_in_lieu_price <= 0 or not math.isfinite(cash_in_lieu_price):
                    raise ValueError("valid cash-in-lieu price is required for a fractional split result")
                cash_credit = fractional * cash_in_lieu_price
                self.realized_pnl += fractional * (cash_in_lieu_price - average_cost)
            if quantity <= VALUE_TOLERANCE:
                del self._positions[ticker]
                self.cash += cash_credit
                return cash_credit
        self._positions[ticker] = BacktestPosition(
            ticker=ticker, quantity=quantity, average_cost=average_cost,
            market_price=market_price,
        )
        self.cash += cash_credit
        return cash_credit

    def apply_dividend(self, ticker: str, dividend_per_share: float) -> float:
        """Credit a non-negative cash dividend; return the credited amount."""
        if dividend_per_share < 0 or not math.isfinite(dividend_per_share):
            raise ValueError("dividend_per_share must be finite and non-negative")
        current = self._positions.get(ticker.strip().upper())
        credit = 0.0 if current is None else current.quantity * dividend_per_share
        self.cash += credit
        return credit

    def mark_to_market(
        self, prices: dict[str, float], as_of: datetime, *, stale_price_tickers: list[str] | None = None,
    ) -> PortfolioSnapshot:
        """Mark every held ticker; missing prices fail without partially updating state."""
        if as_of.tzinfo is None or as_of.utcoffset() is None:
            raise ValueError("as_of must be timezone-aware")
        normalized = {ticker.strip().upper(): price for ticker, price in prices.items()}
        missing = sorted(set(self._positions) - set(normalized))
        if missing:
            raise ValueError(f"missing market prices for held tickers: {missing}")
        for ticker in self._positions:
            price = normalized[ticker]
            if price <= 0 or not math.isfinite(price):
                raise ValueError(f"invalid market price for {ticker}")
        marked = {
            ticker: position.model_copy(update={"market_price": normalized[ticker]})
            for ticker, position in self._positions.items()
        }
        market_value = sum(position.market_value for position in marked.values())
        nav = self.cash + market_value
        weights = ({ticker: position.market_value / nav for ticker, position in marked.items()}
                   if nav > VALUE_TOLERANCE else {})
        cash_weight = self.cash / nav if nav > VALUE_TOLERANCE else 0.0
        exposure = market_value / nav if nav > VALUE_TOLERANCE else 0.0
        self._positions = marked
        return PortfolioSnapshot(
            as_of=as_of, cash=self.cash,
            positions=[marked[ticker] for ticker in sorted(marked)],
            gross_exposure=exposure, net_exposure=exposure,
            market_value=market_value, nav=nav,
            weights={ticker: weights[ticker] for ticker in sorted(weights)},
            cash_weight=cash_weight,
            stale_price_tickers=sorted(stale_price_tickers or []),
            realized_pnl=self.realized_pnl,
            unrealized_pnl=sum(
                (position.market_price - position.average_cost) * position.quantity
                for position in marked.values()
            ),
        )

