from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class LLMRequest(BaseModel):
    agent: str
    task: str
    prompt: str
    ticker: str | None = None
    complexity: str = "standard"
    importance: float = Field(default=0.5, ge=0, le=1)
    max_estimated_cost_usd: float | None = Field(default=None, ge=0)

class LLMResponse(BaseModel):
    provider: str
    model: str
    content: str
    input_tokens: int = 0
    cached_input_tokens: int = 0
    output_tokens: int = 0
    latency_ms: float = 0
    generated_at: datetime
    raw: dict[str, Any] = Field(default_factory=dict)
