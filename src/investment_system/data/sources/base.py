from abc import ABC, abstractmethod
from datetime import datetime
from investment_system.data.schemas.base import PointInTimeRecord

class BaseDataSource(ABC):
    @abstractmethod
    def fetch(self, *, as_of: datetime) -> list[PointInTimeRecord]:
        """Fetch records known as of a timezone-aware instant."""
