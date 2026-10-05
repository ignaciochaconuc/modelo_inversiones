from abc import ABC, abstractmethod
from datetime import date
from investment_system.data.schemas.market import MarketBar

class BaseDataSource(ABC):
    @abstractmethod
    def fetch_daily_bars(self, ticker: str, start_date: date, end_date: date) -> list[MarketBar]:
        """Fetch normalized daily bars for one ticker and inclusive date range."""
