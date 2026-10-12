"""Explicit Responses API model capabilities and parameters; no secrets."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from investment_system.core.time_utils import ensure_utc


class OpenAISettings(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)
    provider: Literal["openai"] = "openai"
    model: str = Field(min_length=1)
    endpoint: Literal["https://api.openai.com/v1/responses"]
    response_mode: Literal["json_schema_strict"]
    max_output_tokens: int = Field(gt=0, le=32768)
    timeout_seconds: float = Field(gt=0, le=120)
    temperature: float | None = Field(default=None, ge=0, le=2)
    reasoning_effort: Literal["minimal", "low", "medium", "high"] | None = None
    capabilities_model: str
    structured_outputs_supported: bool
    capability_max_output_tokens: int = Field(gt=0, le=32768)
    context_window_tokens: int = Field(gt=0)
    supported_parameters: tuple[Literal["temperature", "reasoning_effort"], ...]
    capability_source: str = Field(min_length=1)
    capabilities_verified_at: datetime

    @field_validator("capabilities_verified_at")
    @classmethod
    def utc(cls, value):
        return ensure_utc(value)

    @model_validator(mode="after")
    def capability_check(self):
        if self.model != self.capabilities_model or not self.structured_outputs_supported:
            raise ValueError("matching structured-output model capabilities required")
        if self.max_output_tokens > self.capability_max_output_tokens:
            raise ValueError("configured output cap exceeds the verified model capability")
        for name in ("temperature", "reasoning_effort"):
            if getattr(self, name) is not None and name not in self.supported_parameters:
                raise ValueError("unsupported parameter for configured model")
        return self

    @property
    def effective_parameters(self) -> dict:
        return {"max_output_tokens": self.max_output_tokens,
                **{name: getattr(self, name) for name in ("temperature", "reasoning_effort") if getattr(self, name) is not None}}


class LLMProviderError(RuntimeError):
    """Only safe codes, never provider messages/headers or secret chaining."""
    def __init__(self, code: str, *, retryable: bool = False, response=None):
        super().__init__(code)
        self.code, self.retryable, self.response = code, retryable, response


def strict_transport_schema(schema: dict) -> dict:
    """Structural projection; stronger constraints remain enforced locally."""
    allowed = {"type", "properties", "required", "additionalProperties", "$ref", "$defs", "items", "anyOf", "enum", "const"}
    def project(value):
        if isinstance(value, list):
            return [project(item) for item in value]
        if not isinstance(value, dict):
            return value
        result = {}
        for key, item in value.items():
            if key in allowed:
                result[key] = {name: project(child) for name, child in item.items()} if key in {"properties", "$defs"} else project(item)
        if "const" in result:
            result["enum"] = [result.pop("const")]
        if result.get("type") == "object":
            result["required"] = list(result.get("properties", {}))
            result["additionalProperties"] = False
        return result
    return project(schema)
