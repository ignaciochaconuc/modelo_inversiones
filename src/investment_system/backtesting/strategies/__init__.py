"""Deterministic, non-ML baseline strategies for historical validation."""

from investment_system.backtesting.strategies.base import BaselineStrategy, StrategyPlan
from investment_system.backtesting.strategies.cross_sectional import (
    EqualWeightStrategy, SimpleMomentumStrategy,
)
from investment_system.backtesting.strategies.spy_buy_hold import SpyBuyAndHoldStrategy

__all__ = [
    "BaselineStrategy", "EqualWeightStrategy", "SimpleMomentumStrategy",
    "SpyBuyAndHoldStrategy", "StrategyPlan",
]
