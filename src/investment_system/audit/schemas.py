from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field

class DecisionAuditRecord(BaseModel):
    timestamp: datetime
    decision_id: str
    ticker: str
    features: dict[str, Any]
    model_version: str
    prediction: float | dict[str, float]
    proposed_allocation: float
    risk_decision: dict[str, Any]
    final_action: str
    agent_outputs: list[dict[str, Any]] = Field(default_factory=list)
    source_references: list[dict[str, Any]] = Field(default_factory=list)
    cost_usd: float = Field(default=0, ge=0)
