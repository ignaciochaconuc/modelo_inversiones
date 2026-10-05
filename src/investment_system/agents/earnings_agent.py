from investment_system.agents.stub import StubAgent
from investment_system.core.enums import EarningsMode
class EarningsAgent(StubAgent):
    name = "earnings"
    def __init__(self, mode: EarningsMode) -> None:
        self.mode = mode
