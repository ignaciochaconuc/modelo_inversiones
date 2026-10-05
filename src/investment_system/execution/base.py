from abc import ABC, abstractmethod
from datetime import datetime
from pydantic import BaseModel

class Order(BaseModel):
    ticker: str
    target_weight: float
    submitted_at: datetime

class Fill(BaseModel):
    ticker: str
    filled_weight: float
    price: float
    filled_at: datetime

class BaseExecutor(ABC):
    @abstractmethod
    def execute(self, orders: list[Order]) -> list[Fill]: ...
