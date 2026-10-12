"""Phase 4C.2 wrappers; original 4C.1 interpretation/replay contracts unchanged."""
from datetime import datetime
from typing import Literal

from pydantic import Field, model_validator

from investment_system.data.news_entities import fingerprint
from investment_system.llm.openai_settings import OpenAISettings
from investment_system.llm.pricing import TokenPrice
from investment_system.llm.cost_tracker import LLMCallRecord
from investment_system.agents.news_interpretation.schemas import InterpretationModel, NewsInterpretationRequest, VALIDATION_VERSION
from investment_system.agents.news_interpretation.replay import ReplayEnvelope
from investment_system.llm.schemas import LLMResponse


class PriceSchedule(InterpretationModel):
    provider: Literal["openai"] = "openai"
    model: str
    input_per_million: float = Field(gt=0)
    cached_input_per_million: float = Field(ge=0)
    output_per_million: float = Field(gt=0)
    valid_from: datetime
    valid_until: datetime
    source: str = Field(min_length=1)

    @model_validator(mode="after")
    def interval(self):
        if self.valid_until <= self.valid_from:
            raise ValueError("invalid price validity interval")
        return self

    def token_price(self) -> TokenPrice:
        return TokenPrice(self.input_per_million,self.cached_input_per_million,self.output_per_million)


class InterpretationRuntimeSettings(InterpretationModel):
    settings_version: Literal["news-inference-settings-v1"] = "news-inference-settings-v1"
    adapter: OpenAISettings
    pricing: PriceSchedule
    request_budget_usd: float = Field(gt=0)
    run_budget_usd: float = Field(gt=0)
    max_attempts: int = Field(ge=1, le=4)
    retry_invalid_response: bool
    retry_delay_seconds: float = Field(ge=0, le=10)
    local_content_retention_hours: int = Field(ge=1, le=168)
    local_restricted_storage_acknowledged: bool

    @model_validator(mode="after")
    def explicit_policy(self):
        if self.pricing.model != self.adapter.model or self.pricing.provider != self.adapter.provider:
            raise ValueError("pricing/model identity mismatch")
        if not self.local_restricted_storage_acknowledged:
            raise ValueError("restricted local storage policy must be acknowledged")
        if self.request_budget_usd > self.run_budget_usd:
            raise ValueError("request budget exceeds run budget")
        return self


class StoredInterpretationAttempt(InterpretationModel):
    schema_version: Literal["news-inference-attempt-v1"] = "news-inference-attempt-v1"
    attempt_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    cache_key: str = Field(pattern=r"^[a-f0-9]{64}$")
    run_id: str
    attempt_number: int = Field(gt=0)
    request: NewsInterpretationRequest
    settings: InterpretationRuntimeSettings
    started_at: datetime
    received_at: datetime
    persisted_at: datetime
    expires_at: datetime
    requested_provider: str
    requested_model: str
    actual_model: str | None
    effective_parameters: dict
    wire_fingerprint: str
    wire_payload: dict = Field(repr=False)
    maximum_reserved_usd: float = Field(ge=0)
    accounted_usd: float = Field(ge=0)
    observed_usage_cost_usd: float | None = Field(default=None, ge=0)
    cost_record: LLMCallRecord
    provider_response: LLMResponse | None = Field(default=None, repr=False)
    interpretation: ReplayEnvelope | None = None
    outcome: str
    error_code: str | None
    dataset_role: Literal["exploratory_real_response", "offline_simulated_development"]

    @model_validator(mode="after")
    def consistency(self):
        if not self.started_at <= self.received_at <= self.persisted_at < self.expires_at:
            raise ValueError("invalid attempt chronology/retention")
        if self.requested_model != self.settings.adapter.model or self.requested_provider != "openai":
            raise ValueError("stored route identity mismatch")
        if self.effective_parameters != self.settings.adapter.effective_parameters:
            raise ValueError("stored effective parameters mismatch")
        if fingerprint(self.wire_payload) != self.wire_fingerprint:
            raise ValueError("stored wire payload hash mismatch")
        expected_key=fingerprint({"request":self.request.request_id,"evidence":self.request.evidence_fingerprint,
            "validation_version":VALIDATION_VERSION,"settings":self.settings.model_dump(mode="json"),"wire":self.wire_payload})
        if self.cache_key != expected_key:
            raise ValueError("stored cache identity does not bind its exact request/settings")
        if self.wire_payload.get("model") != self.requested_model or self.wire_payload.get("tools") != [] or self.wire_payload.get("store") is not False:
            raise ValueError("unauthorized stored transport configuration")
        if self.provider_response and self.provider_response.raw:
            raise ValueError("raw provider metadata must be whitelisted out of durable response")
        if self.provider_response and self.actual_model != self.provider_response.model:
            raise ValueError("actual model and durable provider response mismatch")
        if self.accounted_usd != (self.maximum_reserved_usd if self.observed_usage_cost_usd is None else self.observed_usage_cost_usd):
            raise ValueError("accounted cost/reservation mismatch")
        if self.cost_record.estimated_cost_usd != self.observed_usage_cost_usd:
            raise ValueError("cost provenance mismatch")
        if self.interpretation:
            if self.interpretation.request != self.request or self.interpretation.result.status != self.outcome:
                raise ValueError("interpretation/request outcome mismatch")
            if self.provider_response is None or self.actual_model != self.requested_model:
                raise ValueError("accepted interpretation requires verified actual model")
            durable=self.provider_response.model_dump(mode="json",exclude={"raw"})
            recorded=self.interpretation.result.provenance.model_dump(mode="json",exclude={"tokens_reported","latency_reported"})
            if durable != recorded:
                raise ValueError("interpreted and durable provider responses differ")
            if self.interpretation.result.available_at > self.persisted_at:
                raise ValueError("persisted interpretation predates its availability")
        return self

    @property
    def record_id(self) -> str:
        return fingerprint(self.model_dump(mode="json"))


class InterpretationDelivery(InterpretationModel):
    retrieval_mode: Literal["new_inference", "exact_cache_recovery", "offline_reconstruction"]
    cache_key: str
    record_id: str | None = None
    attempt_record_ids: tuple[str,...] = ()
    record: StoredInterpretationAttempt | None = None
    error_code: str | None = None
    additional_provider_cost_usd: float | None = None
    additional_attempts: int = 0
