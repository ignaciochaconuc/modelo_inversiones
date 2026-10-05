from pydantic import BaseModel, Field
from investment_system.core.enums import RiskAction
from investment_system.portfolio.state import AllocationProposal
from investment_system.risk.rules import RiskLimits

class RiskDecision(BaseModel):
    action: RiskAction
    approved_weights: dict[str, float] = Field(default_factory=dict)
    reasons: list[str] = Field(default_factory=list)

class RiskManager:
    """Independent authority; execution accepts only its approved weights."""
    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits
    def evaluate(self, proposal: AllocationProposal) -> RiskDecision:
        reasons: list[str] = []
        if any(weight < 0 for weight in proposal.weights.values()) and self.limits.long_only:
            return RiskDecision(action=RiskAction.BLOCK, reasons=["short positions are forbidden"])
        positive = {ticker: weight for ticker, weight in proposal.weights.items() if weight > 0}
        if len(positive) > self.limits.max_positions:
            return RiskDecision(action=RiskAction.BLOCK, reasons=["maximum number of positions exceeded"])
        capped = {ticker: min(weight, self.limits.max_position_weight) for ticker, weight in positive.items()}
        if capped != positive:
            reasons.append("one or more positions were capped")
        exposure = sum(capped.values())
        if exposure > self.limits.max_portfolio_exposure:
            return RiskDecision(action=RiskAction.BLOCK, reasons=["maximum portfolio exposure exceeded"])
        action = RiskAction.REDUCE if reasons else RiskAction.APPROVE
        return RiskDecision(action=action, approved_weights=capped, reasons=reasons)
