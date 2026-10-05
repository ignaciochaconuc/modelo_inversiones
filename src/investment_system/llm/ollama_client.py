from investment_system.core.exceptions import ExternalCallDisabled
from investment_system.llm.base import BaseLLMClient
from investment_system.llm.schemas import LLMRequest, LLMResponse

class OllamaClient(BaseLLMClient):
    provider = "ollama"
    def complete(self, request: LLMRequest, model: str) -> LLMResponse:
        raise ExternalCallDisabled("Ollama calls are deliberately not implemented in phase zero")
