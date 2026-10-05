from investment_system.core.exceptions import ExternalCallDisabled
from investment_system.llm.base import BaseLLMClient
from investment_system.llm.schemas import LLMRequest, LLMResponse

class OpenAIClient(BaseLLMClient):
    provider = "openai"
    def complete(self, request: LLMRequest, model: str) -> LLMResponse:
        raise ExternalCallDisabled("OpenAI calls are deliberately not implemented in phase zero")
