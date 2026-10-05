from datetime import datetime, timezone
from investment_system.core.enums import RiskAction
from investment_system.portfolio.state import AllocationProposal
from investment_system.risk.manager import RiskManager
from investment_system.risk.rules import RiskLimits

def test_risk_manager_caps_position() -> None:
    proposal = AllocationProposal(generated_at=datetime.now(timezone.utc), weights={"AAPL": 0.2}, cash_weight=0.8)
    decision = RiskManager(RiskLimits()).evaluate(proposal)
    assert decision.action == RiskAction.REDUCE
    assert decision.approved_weights["AAPL"] == 0.1
