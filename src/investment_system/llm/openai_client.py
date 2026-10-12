"""Opt-in Responses REST adapter; retry/accounting belong to the budget owner."""
from datetime import datetime, timezone
import os
import time

import httpx

from investment_system.core.exceptions import ExternalCallDisabled
from investment_system.llm.base import BaseLLMClient
from investment_system.llm.schemas import LLMRequest, LLMResponse
from investment_system.llm.openai_settings import LLMProviderError, OpenAISettings, strict_transport_schema


class OpenAIClient(BaseLLMClient):
    provider = "openai"

    def __init__(self, settings: OpenAISettings | None = None, *, enabled: bool = False,
                 transport: httpx.BaseTransport | None = None):
        self.settings, self.enabled, self.transport = settings, enabled, transport

    def wire_payload(self, request: LLMRequest, model: str) -> dict:
        if self.settings is None or model != self.settings.model:
            raise LLMProviderError("model_configuration_mismatch")
        if request.response_schema is None:
            raise LLMProviderError("structured_schema_required")
        prefix, separator, data = request.prompt.partition("{")
        if not separator:
            raise LLMProviderError("structured_prompt_required")
        return {"model": model, "instructions": prefix, "input": "{" + data,
                "text": {"format": {"type": "json_schema", "name": "news_interpretation",
                                     "strict": True, "schema": strict_transport_schema(request.response_schema)}},
                "store": False, "background": False, "tools": [], **self.settings.effective_parameters}

    def complete(self, request: LLMRequest, model: str) -> LLMResponse:
        if not self.enabled or self.settings is None:
            raise ExternalCallDisabled("OpenAI adapter requires explicit enablement/configuration")
        payload = self.wire_payload(request, model)
        key = os.getenv("OPENAI_API_KEY")
        if not key:
            raise LLMProviderError("missing_api_key")
        started = time.monotonic()
        try:
            with httpx.Client(transport=self.transport, timeout=self.settings.timeout_seconds,
                              follow_redirects=False, trust_env=False) as client:
                http = client.post(self.settings.endpoint, headers={"Authorization": "Bearer " + key}, json=payload)
        except httpx.TimeoutException:
            raise LLMProviderError("timeout", retryable=True) from None
        except httpx.TransportError:
            raise LLMProviderError("disconnect", retryable=True) from None
        if http.status_code != 200:
            retryable = http.status_code == 429 or 500 <= http.status_code <= 599
            code = "authentication" if http.status_code == 401 else "authorization" if http.status_code == 403 else "rate_limit" if http.status_code == 429 else "server_error" if http.status_code >= 500 else "permanent_http_error"
            raise LLMProviderError(code, retryable=retryable) from None
        try:
            body = http.json()
            actual_model = body["model"]
            generated = datetime.fromtimestamp(body["created_at"], timezone.utc)
            messages = [part for item in body.get("output", []) if item.get("type") == "message" for part in item.get("content", [])]
            content = "".join(part["text"] for part in messages if part.get("type") == "output_text")
            usage = body.get("usage") or {}
            counts = {}
            if all(isinstance(usage.get(n), int) and not isinstance(usage.get(n), bool) and usage[n] >= 0 for n in ("input_tokens", "output_tokens")):
                counts = dict(input_tokens=usage["input_tokens"], output_tokens=usage["output_tokens"])
                cached = usage.get("input_tokens_details", {}).get("cached_tokens")
                if isinstance(cached, int) and not isinstance(cached, bool) and 0 <= cached <= usage["input_tokens"]:
                    counts["cached_input_tokens"] = cached
            response = LLMResponse(provider="openai", model=actual_model, content=content,
                generated_at=generated, latency_ms=(time.monotonic()-started)*1000, **counts,
                raw={"status": body.get("status"), "received_at": datetime.now(timezone.utc).isoformat(),
                     "effective_parameters": self.settings.effective_parameters,
                     "usage_reported": len(counts) == 3 and body.get("status") not in {"queued","in_progress"}, "requested_model": model})
            # Kept outside LLMResponse's legacy serialized contract and persisted
            # by the v2 attempt wrapper. Missing is unknown, never implicit zero.
            written = usage.get("input_tokens_details", {}).get("cache_write_tokens")
            if type(written) is int and written >= 0:
                response.raw["cache_write_tokens"] = written
        except (ValueError, KeyError, TypeError, AttributeError, OverflowError):
            raise LLMProviderError("invalid_provider_envelope", retryable=True) from None
        if key in content or key in actual_model:
            response.content = ""
            if key in actual_model:
                response.model = "redacted_unknown_model"
            raise LLMProviderError("secret_echo_rejected", response=response)
        if actual_model != model:
            raise LLMProviderError("model_identity_mismatch", response=response)
        if any(part.get("type") == "refusal" for part in messages):
            raise LLMProviderError("provider_refusal", response=response)
        if body.get("status") == "failed":
            provider_code=(body.get("error") or {}).get("code")
            code="server_error" if provider_code=="server_error" else "rate_limit" if provider_code=="rate_limit_exceeded" else "permanent_provider_error"
            raise LLMProviderError(code,retryable=code in {"server_error","rate_limit"},response=response)
        if body.get("status") in {"queued","in_progress","cancelled"}:
            raise LLMProviderError("unexpected_pending_or_cancelled_response",response=response)
        if body.get("status") != "completed":
            raise LLMProviderError("incomplete_response", retryable=True, response=response)
        if any(item.get("type") not in {"message","reasoning"} for item in body.get("output",[])):
            raise LLMProviderError("unexpected_provider_tool",response=response)
        return response
