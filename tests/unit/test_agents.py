from datetime import datetime, timezone
from investment_system.agents.base import AgentContext, AgentResponse
from investment_system.agents.news_agent import NewsAgent

def test_agent_response_round_trip() -> None:
    now = datetime.now(timezone.utc)
    response = NewsAgent().analyze(AgentContext(ticker="AAPL", as_of=now, decision_time=now))
    restored = AgentResponse.model_validate_json(response.model_dump_json())
    assert restored.ticker == "AAPL"
    assert restored.confidence == 0
