from typing import Any
from investment_system.llm.base import BaseLLMClient
from investment_system.llm.schemas import LLMRequest, LLMResponse

class LLMRouter:
    def __init__(self, clients: dict[str, BaseLLMClient], routes: dict[str, dict[str, Any]]) -> None:
        self.clients, self.routes = clients, routes
    def select(self, request: LLMRequest) -> tuple[BaseLLMClient, str]:
        route = self.routes.get(request.task) or self.routes.get(f"{request.agent}.{request.task}") or self.routes.get("default")
        if not route:
            raise ValueError(f"no LLM route for {request.agent}.{request.task}")
        provider = route["provider"]
        if provider not in self.clients:
            raise ValueError(f"LLM client not configured: {provider}")
        return self.clients[provider], route["model"]
    def complete(self, request: LLMRequest) -> LLMResponse:
        client, model = self.select(request)
        return client.complete(request, model)
