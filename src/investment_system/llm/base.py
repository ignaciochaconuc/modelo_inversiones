from abc import ABC, abstractmethod
from investment_system.llm.schemas import LLMRequest, LLMResponse

class BaseLLMClient(ABC):
    provider: str
    @abstractmethod
    def complete(self, request: LLMRequest, model: str) -> LLMResponse:
        """Complete a routed request."""
