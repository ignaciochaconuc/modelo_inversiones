from abc import ABC, abstractmethod
from datetime import date
from typing import Any

class BaseBacktestEngine(ABC):
    """Contract enforcing decisions after close and fills at next session open."""
    @abstractmethod
    def run(self, start: date, end: date) -> Any: ...
