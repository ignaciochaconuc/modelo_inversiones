"""Reusable SPY buy-and-hold baseline with causal dividend reinvestment."""
from __future__ import annotations

from datetime import date

from investment_system.backtesting.strategies.base import (
    StrategyPlan, buy_and_hold_allocations,
)
from investment_system.data.calendar import TradingCalendar
from investment_system.data.storage.market_store import MarketDataStore


class SpyBuyAndHoldStrategy:
    strategy_name = "spy_buy_hold"
    strategy_version = "spy-buy-hold-v1"

    def __init__(
        self,
        market_store: MarketDataStore,
        calendar: TradingCalendar,
        *,
        ticker: str = "SPY",
        timezone_name: str = "America/New_York",
        decision_cutoff: str = "20:15",
    ) -> None:
        self.market_store = market_store
        self.calendar = calendar
        self.ticker = ticker.strip().upper()
        self.timezone_name = timezone_name
        self.decision_cutoff = decision_cutoff

    def generate_allocations(self, start: date, end: date) -> StrategyPlan:
        allocations = buy_and_hold_allocations(
            ticker=self.ticker,
            start=start,
            end=end,
            calendar=self.calendar,
            actions=self.market_store.read_actions(self.ticker),
            timezone_name=self.timezone_name,
            cutoff=self.decision_cutoff,
        )
        return StrategyPlan(
            strategy_name=self.strategy_name,
            strategy_version=self.strategy_version,
            allocations=allocations,
        )
