from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from pydantic import BaseModel, ConfigDict, Field

class SourceReference(BaseModel):
    name: str
    url: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime

class AgentContext(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str | None = None
    as_of: datetime
    decision_time: datetime
    documents: list[dict[str, Any]] = Field(default_factory=list)
    quantitative_features: dict[str, float | str | bool | None] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

class AgentResponse(BaseModel):
    ticker: str | None = None
    generated_at: datetime
    as_of: datetime
    confidence: float = Field(ge=0, le=1)
    sources: list[SourceReference] = Field(default_factory=list)
    bull_case: str
    bear_case: str
    risks: list[str] = Field(default_factory=list)
    summary: str
    structured_features: dict[str, float | str | bool | None] = Field(default_factory=dict)

class BaseAgent(ABC):
    name: str
    @abstractmethod
    def analyze(self, context: AgentContext) -> AgentResponse:
        """Produce human-readable analysis and ML-ready structured features."""
