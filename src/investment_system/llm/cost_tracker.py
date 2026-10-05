from datetime import date, datetime
from pydantic import BaseModel, Field

class LLMCallRecord(BaseModel):
    timestamp: datetime
    provider: str
    model: str
    agent: str
    task: str
    ticker: str | None = None
    analysis_id: str | None = None
    trade_id: str | None = None
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    total_tokens: int = Field(ge=0)
    estimated_cost_usd: float = Field(ge=0)
    latency_ms: float = Field(ge=0)
    success: bool
    error_type: str | None = None

class CostTracker:
    def __init__(self) -> None:
        self.records: list[LLMCallRecord] = []
    def add(self, record: LLMCallRecord) -> None:
        if record.total_tokens != record.input_tokens + record.output_tokens:
            raise ValueError("total_tokens must equal input_tokens + output_tokens")
        self.records.append(record)
    def _sum(self, predicate=lambda _: True) -> float:
        return sum(r.estimated_cost_usd for r in self.records if predicate(r))
    def by_agent(self, agent: str) -> float: return self._sum(lambda r: r.agent == agent)
    def by_ticker(self, ticker: str) -> float: return self._sum(lambda r: r.ticker == ticker)
    def daily(self, day: date) -> float: return self._sum(lambda r: r.timestamp.date() == day)
    def monthly(self, year: int, month: int) -> float: return self._sum(lambda r: (r.timestamp.year, r.timestamp.month) == (year, month))
    def by_analysis(self, analysis_id: str) -> float: return self._sum(lambda r: r.analysis_id == analysis_id)
    def by_trade(self, trade_id: str) -> float: return self._sum(lambda r: r.trade_id == trade_id)
