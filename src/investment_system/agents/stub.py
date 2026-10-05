from datetime import datetime, timezone
from investment_system.agents.base import AgentContext, AgentResponse, BaseAgent

class StubAgent(BaseAgent):
    name = "stub"
    def analyze(self, context: AgentContext) -> AgentResponse:
        return AgentResponse(
            ticker=context.ticker, generated_at=datetime.now(timezone.utc), as_of=context.as_of,
            confidence=0.0, bull_case="Not evaluated", bear_case="Not evaluated",
            risks=["Phase-zero stub: no external evidence was analyzed"],
            summary=f"{self.name} is not connected to external data.", structured_features={},
        )
