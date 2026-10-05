from abc import ABC, abstractmethod
from investment_system.portfolio.state import AllocationProposal, AssetForecast, PortfolioState

class BasePortfolioOptimizer(ABC):
    """Future objective: return - risk_aversion*risk - transaction costs."""
    @abstractmethod
    def optimize(self, forecasts: list[AssetForecast], current: PortfolioState) -> AllocationProposal: ...
