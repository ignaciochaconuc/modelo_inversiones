"""Versioned evidence-first news interpretation contracts, experimental only."""
from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from investment_system.core.time_utils import ensure_utc
from investment_system.data.news_entities import fingerprint
from investment_system.data.schemas.news import NewsQueryMode, NewsRecord
from investment_system.data.schemas.news_enrichment import EntityRegistryEntry


SCHEMA_VERSION = "news-interpretation-v1"
PROMPT_VERSION = "news-interpretation-prompt-v1"
TAXONOMY_VERSION = "news-event-taxonomy-v1"
VALIDATION_VERSION = "news-interpretation-validation-v1"
Digest = str
EventType = Literal["earnings", "guidance", "investment", "financing", "ma", "regulation",
                    "litigation", "product", "partnership", "management", "macro", "analyst_opinion", "other"]
AbstentionReason = Literal["generic_headline", "unidentified_actor", "unverifiable_opinion",
                          "unattributed_rumor", "inseparable_multiple_events", "contradictory_evidence",
                          "insufficient_evidence"]


class InterpretationModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    @field_validator("*", mode="after")
    @classmethod
    def utc(cls, value):
        return ensure_utc(value) if isinstance(value, datetime) else value


class TextEvidence(InterpretationModel):
    news_id: str
    revision_id: str
    field: Literal["headline", "summary"]
    text: str = Field(min_length=1, repr=False)
    available_at: datetime

    @property
    def evidence_id(self) -> Digest:
        return fingerprint(self.model_dump(mode="json"))


class EvidenceSpan(InterpretationModel):
    """Exact half-open Python Unicode character offsets; never fuzzy citations."""
    evidence_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    start: int = Field(ge=0)
    end: int = Field(gt=0)
    quote: str = Field(min_length=1, repr=False)

    @model_validator(mode="after")
    def offsets(self):
        if self.end <= self.start or self.end - self.start != len(self.quote):
            raise ValueError("evidence span length/offset mismatch")
        return self


class InterpretationTarget(InterpretationModel):
    """Analysis scope, not evidence that provider ticker is the event actor."""
    ticker: str | None = None
    entity_id: str | None = None


class SnapshotReference(InterpretationModel):
    snapshot_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    decision_time: datetime
    computed_at: datetime
    available_at: datetime
    registry_fingerprint: str
    algorithm_version: str
    temporal_status: Literal["strict_inputs", "historical_research_unverified"]
    cluster_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def availability(self):
        if self.available_at < self.computed_at:
            raise ValueError("computed cluster context cannot predate computation")
        return self


class NewsInterpretationRequest(InterpretationModel):
    schema_version: Literal["news-interpretation-v1"] = SCHEMA_VERSION
    prompt_version: Literal["news-interpretation-prompt-v1"] = PROMPT_VERSION
    taxonomy_version: Literal["news-event-taxonomy-v1"] = TAXONOMY_VERSION
    decision_time: datetime
    mode: NewsQueryMode = NewsQueryMode.STRICT
    allow_historical_proxy: bool = False
    allow_retrospective_registry: bool = False
    news: NewsRecord
    context_news: tuple[NewsRecord, ...] = ()
    registry_entries: tuple[EntityRegistryEntry, ...] = ()
    snapshot: SnapshotReference | None = None
    target: InterpretationTarget | None = None

    @model_validator(mode="after")
    def causal_request(self):
        records = (self.news, *self.context_news)
        if len({r.news_id for r in records}) != len(records):
            raise ValueError("context duplicates primary/logical article identity")
        if self.mode == NewsQueryMode.STRICT and (self.allow_historical_proxy or self.allow_retrospective_registry):
            raise ValueError("strict interpretation cannot opt into retrospective evidence")
        for record in records:
            effective = record.historical_proxy_at if self.allow_historical_proxy and record.historical_proxy_at else record.available_at
            if effective > self.decision_time:
                raise ValueError("future or ineligible news revision")
            if self.mode == NewsQueryMode.STRICT and max(record.first_seen_at, record.ingested_at) > self.decision_time:
                raise ValueError("strict text cannot be retrieved/ingested after the cutoff")
        fact_date = (self.news.published_at or self.news.available_at).date()
        for entry in self.registry_entries:
            if not self.allow_retrospective_registry and entry.known_at > self.decision_time:
                raise ValueError("future registry entry")
            if not entry.effective_from <= fact_date or (entry.effective_to and fact_date >= entry.effective_to):
                raise ValueError("registry entry outside effective interval")
        if self.target and self.target.entity_id and self.target.entity_id not in {e.entity_id for e in self.registry_entries}:
            raise ValueError("target entity lacks eligible registry evidence")
        if self.snapshot:
            if self.snapshot.decision_time > self.decision_time:
                raise ValueError("future snapshot cutoff")
            if self.mode == NewsQueryMode.STRICT and (
                self.snapshot.available_at > self.decision_time or self.snapshot.temporal_status != "strict_inputs"
            ):
                raise ValueError("future/unverified computed cluster context")
        return self

    @property
    def news_id(self) -> str:
        return self.news.news_id

    @property
    def revision_id(self) -> str:
        return self.news.revision_id

    @property
    def evidence(self) -> tuple[TextEvidence, ...]:
        return tuple(TextEvidence(news_id=r.news_id, revision_id=r.revision_id, field=field,
                                  text=getattr(r, field), available_at=r.available_at)
                     for r in (self.news, *self.context_news) for field in ("headline", "summary") if getattr(r, field))

    @property
    def request_id(self) -> Digest:
        return fingerprint(self.model_dump(mode="json"))

    @property
    def evidence_fingerprint(self) -> Digest:
        return fingerprint([e.model_dump(mode="json") for e in self.evidence])

    @property
    def inputs_available_at(self) -> datetime:
        return max([moment for r in (self.news, *self.context_news)
                    for moment in (r.available_at, r.first_seen_at, r.ingested_at)]
                   + [e.known_at for e in self.registry_entries]
                   + ([self.snapshot.available_at] if self.snapshot else []))


class EventEntity(InterpretationModel):
    name: str = Field(min_length=1)
    role: Literal["actor", "counterparty", "regulator", "subject", "unknown"]
    entity_id: str | None = None
    ticker: str | None = None
    evidence: EvidenceSpan


class NumericClaim(InterpretationModel):
    """Value as printed; unit/scale null when absent, never silently converted."""
    metric: str = Field(min_length=1)
    value: Decimal
    value_text: str = Field(min_length=1)
    unit: str | None
    scale: Literal["one", "thousand", "million", "billion"] | None = None
    period: str | None = None
    context: EvidenceSpan

    @model_validator(mode="after")
    def numeric_fidelity(self):
        try:
            lexical = Decimal(self.value_text.replace(",", ""))
        except InvalidOperation as exc:
            raise ValueError("unparseable source number") from exc
        if not lexical.is_finite() or not self.value.is_finite() or lexical != self.value:
            raise ValueError("invented or transformed numerical value")
        if not re.search(r"(?<![\w.,+\-])" + re.escape(self.value_text) + r"(?![\w.,])", self.context.quote):
            raise ValueError("source number absent from cited context")
        if self.unit and self.unit not in self.context.quote:
            raise ValueError("invented unit")
        if self.scale and self.scale != "one" and self.scale not in self.context.quote:
            raise ValueError("invented numerical scale")
        if self.period and self.period not in self.context.quote:
            raise ValueError("invented reporting period")
        return self


class ExtractedNewsEvent(InterpretationModel):
    event_key: str = Field(min_length=1)
    event_type: EventType
    other_type: str | None = Field(default=None, min_length=1)
    description: str = Field(min_length=1)
    state: Literal["confirmed", "expected", "opinion", "rumor", "ambiguous"]
    stage: Literal["proposed", "announced", "completed", "unknown"] = "unknown"
    negated: bool = False
    state_evidence: EvidenceSpan
    entities: tuple[EventEntity, ...] = ()
    event_date: date | None = None
    date_evidence: EvidenceSpan | None = None
    evidence: tuple[EvidenceSpan, ...] = Field(min_length=1)
    numbers: tuple[NumericClaim, ...] = ()
    unknown_fields: tuple[str, ...] = ()

    @model_validator(mode="after")
    def factual_structure(self):
        if (self.event_type == "other") != (self.other_type is not None):
            raise ValueError("other event types require an explicit label; version taxonomy to extend")
        if (self.event_date is None) != (self.date_evidence is None):
            raise ValueError("event date requires textual evidence")
        if self.event_date and self.event_date.isoformat() not in self.date_evidence.quote:
            raise ValueError("event date not explicitly supported in ISO source form")
        return self


class EconomicClaim(InterpretationModel):
    text: str = Field(min_length=1)
    category: Literal["reported_fact", "inference", "unknown"]
    evidence: tuple[EvidenceSpan, ...] = ()
    rationale: str | None = None

    @model_validator(mode="after")
    def discipline(self):
        if self.category == "reported_fact" and not self.evidence:
            raise ValueError("reported fact requires exact source evidence")
        if self.category == "inference" and not self.rationale:
            raise ValueError("inference requires an explicit reasoning rationale")
        return self


class EconomicInterpretation(InterpretationModel):
    favorable: tuple[EconomicClaim, ...] = ()
    unfavorable: tuple[EconomicClaim, ...] = ()
    horizon: Literal["immediate", "near_term", "long_term", "unknown"] = "unknown"
    materiality: Literal["limited", "potentially_material", "unknown"] = "unknown"
    stance: Literal["not_assessed", "balanced", "neutral", "uncertain"] = "not_assessed"
    uncertainty: tuple[str, ...] = ()
    evidence_limitations: tuple[str, ...] = ()


class InterpretationPayload(InterpretationModel):
    """Only these semantic fields can come from model JSON, never provenance."""
    schema_version: Literal["news-interpretation-v1"] = SCHEMA_VERSION
    status: Literal["interpreted", "abstained"]
    events: tuple[ExtractedNewsEvent, ...] = ()
    economics: EconomicInterpretation = Field(default_factory=EconomicInterpretation)
    abstention_reasons: tuple[AbstentionReason, ...] = ()
    evidence_sufficiency: Literal["insufficient", "limited", "substantial", "unknown"] = "unknown"

    @model_validator(mode="after")
    def semantic_outcome(self):
        if len({e.event_key for e in self.events}) != len(self.events):
            raise ValueError("duplicate extracted event keys")
        if self.status == "interpreted" and (not self.events or self.abstention_reasons):
            raise ValueError("interpreted outcome needs events and no whole-article abstention")
        if self.status == "abstained" and (self.events or not self.abstention_reasons or self.economics.favorable or self.economics.unfavorable):
            raise ValueError("abstention is not a fabricated neutral event/interpretation")
        if self.status == "abstained" and self.economics.stance in {"neutral", "balanced"}:
            raise ValueError("insufficient evidence is not a neutral economic assessment")
        return self


class ModelConfiguration(InterpretationModel):
    """Planned settings; 4C.1 does not transport/enforce them on real clients."""
    configuration_version: Literal["news-interpretation-model-config-v1"] = "news-interpretation-model-config-v1"
    provider: str = Field(min_length=1)
    model: str = Field(min_length=1)
    model_revision: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_output_tokens: int | None = Field(default=None, gt=0)
    seed: int | None = None
    max_estimated_cost_usd: float | None = Field(default=None, ge=0)


class RecordedLLMResponse(InterpretationModel):
    """Whitelist existing LLMResponse fields; never copy raw headers/secrets."""
    provider: str
    model: str
    content: str = Field(repr=False)
    generated_at: datetime
    input_tokens: int = Field(ge=0)
    cached_input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    latency_ms: float = Field(ge=0)
    tokens_reported: bool = False
    latency_reported: bool = False

    @model_validator(mode="after")
    def usage(self):
        if self.cached_input_tokens > self.input_tokens:
            raise ValueError("cached tokens exceed total input tokens")
        return self


class NewsInterpretationResult(InterpretationModel):
    schema_version: Literal["news-interpretation-v1"] = SCHEMA_VERSION
    prompt_version: Literal["news-interpretation-prompt-v1"] = PROMPT_VERSION
    taxonomy_version: Literal["news-event-taxonomy-v1"] = TAXONOMY_VERSION
    validation_version: Literal["news-interpretation-validation-v1"] = VALIDATION_VERSION
    request_id: str
    news_id: str
    revision_id: str
    evidence_fingerprint: str
    invocation_fingerprint: str
    response_fingerprint: str
    decision_time: datetime
    query_mode: NewsQueryMode
    allow_historical_proxy: bool
    allow_retrospective_registry: bool
    inputs_available_at: datetime
    generated_at: datetime
    validated_at: datetime
    available_at: datetime
    use_policy: Literal["experimental_only_not_operational"] = "experimental_only_not_operational"
    execution_mode: Literal["simulated_replay", "retrospective_reconstruction"]
    status: Literal["interpreted", "abstained", "invalid_response", "budget_exceeded", "technical_error"]
    payload: InterpretationPayload | None = None
    error_code: Literal["invalid_structured_evidence", "supplied_estimate_exceeds_budget", "transport_error", "timeout"] | None = None
    estimated_cost_usd: float | None = Field(default=None, ge=0)
    cost_basis: Literal["supplied_estimate", "not_available"] = "not_available"
    model_configuration: ModelConfiguration
    provenance: RecordedLLMResponse

    @model_validator(mode="after")
    def result_times(self):
        if self.query_mode == NewsQueryMode.STRICT and (self.allow_historical_proxy or self.allow_retrospective_registry):
            raise ValueError("strict result cannot declare retrospective opt-ins")
        if self.validated_at < self.generated_at:
            raise ValueError("validation cannot predate actual generation")
        if self.generated_at < self.inputs_available_at:
            raise ValueError("generation predates actual input availability")
        if self.available_at != max(self.generated_at, self.validated_at, self.inputs_available_at):
            raise ValueError("derived availability must include real generation and validation")
        if self.provenance.generated_at != self.generated_at:
            raise ValueError("generation provenance mismatch")
        if (self.provenance.provider, self.provenance.model) != (self.model_configuration.provider, self.model_configuration.model):
            raise ValueError("provider/model provenance mismatch")
        if (self.status in {"interpreted", "abstained"}) != (self.payload is not None):
            raise ValueError("payload and execution outcome mismatch")
        if self.payload and self.payload.status != self.status:
            raise ValueError("semantic status mismatch")
        expected_errors = {"invalid_response": "invalid_structured_evidence",
                           "budget_exceeded": "supplied_estimate_exceeds_budget"}
        if self.status in {"interpreted", "abstained"} and self.error_code is not None:
            raise ValueError("valid semantic outcome cannot be a technical failure")
        if self.status in expected_errors and self.error_code != expected_errors[self.status]:
            raise ValueError("error code and execution outcome mismatch")
        if self.status == "technical_error" and self.error_code not in {"transport_error", "timeout"}:
            raise ValueError("technical error requires a safe enumerated reason")
        if (self.estimated_cost_usd is None) != (self.cost_basis == "not_available"):
            raise ValueError("unknown pricing must remain unknown, not zero")
        return self

    @property
    def result_id(self) -> Digest:
        return fingerprint(self.model_dump(mode="json"))

    def operationally_eligible_at(self, decision_time: datetime) -> bool:
        """No 4C.1 replay/simulation is authorized for operational decisions."""
        ensure_utc(decision_time)
        return False
