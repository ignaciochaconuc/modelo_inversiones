"""Auditable contracts for deterministic Phase 4B news reconstruction."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from investment_system.core.time_utils import ensure_utc
from investment_system.data.schemas.news import NewsRecord


class EnrichmentModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", mode="after")
    @classmethod
    def normalize_datetime(cls, value):
        return ensure_utc(value) if isinstance(value, datetime) else value


class EntityRegistryEntry(EnrichmentModel):
    entity_id: str
    corporate_name: str
    security_id: str
    ticker: str
    share_class: str | None = None
    aliases: tuple[str, ...] = ()
    effective_from: date
    effective_to: date | None = None
    known_at: datetime
    evidence: str = Field(min_length=1)

    @field_validator("known_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)

    @model_validator(mode="after")
    def valid_interval(self) -> "EntityRegistryEntry":
        if self.effective_to and self.effective_to <= self.effective_from:
            raise ValueError("effective_to is exclusive and must follow effective_from")
        return self


class NewsEntityRegistry(EnrichmentModel):
    version: str
    entries: tuple[EntityRegistryEntry, ...]
    universe_description: str


class NewsGroupingParameters(EnrichmentModel):
    algorithm_version: str = "news-groups-v1"
    resolver_version: str = "entity-resolver-v1"
    text_version: str = "unicode-word-bigram-v1"
    editorial_threshold: float = Field(default=0.90, ge=0, le=1)
    event_threshold: float = Field(default=0.55, ge=0, le=1)
    headline_threshold: float = Field(default=0.65, ge=0, le=1)
    max_hours: float = Field(default=48, gt=0)
    minimum_tokens: int = Field(default=8, ge=3)
    max_candidates: int = Field(default=100000, gt=0)


class NewsEntityLink(EnrichmentModel):
    link_id: str
    news_id: str
    revision_id: str
    entity_id: str | None
    security_id: str | None
    ticker: str | None
    evidence_type: Literal["provider_ticker", "explicit_ticker", "corporate_alias", "unresolved"]
    matched_text: str
    status: Literal["resolved", "ambiguous_security", "ambiguous_entity", "unresolved"]
    candidates: tuple[str, ...] = ()
    registry_version: str
    resolver_version: str
    available_at: datetime
    temporal_status: Literal["strict_inputs", "retrospective_registry", "unverified_proxy"]
    evidence: tuple[str, ...] = ()


class NewsPairEvidence(EnrichmentModel):
    left_revision_id: str
    right_revision_id: str
    relationship: Literal["exact_duplicate", "editorial_duplicate", "shared_event", "different"]
    similarity: float = Field(ge=0, le=1)
    headline_similarity: float = Field(ge=0, le=1)
    hours_apart: float = Field(ge=0)
    common_entities: tuple[str, ...]
    reasons: tuple[str, ...]
    available_at: datetime


class NewsDedupRecord(EnrichmentModel):
    group_id: str
    relationship: Literal["exact_duplicate", "editorial_duplicate"]
    members: tuple[str, ...]
    representative_revision_id: str
    available_at: datetime
    evidence_pairs: tuple[NewsPairEvidence, ...]


class NewsEventCluster(EnrichmentModel):
    cluster_id: str
    identity_policy: str = "snapshot_membership_sha256_not_stable_event_identity"
    members: tuple[str, ...]
    representative_revision_id: str
    entity_ids: tuple[str, ...]
    available_at: datetime
    evidence_pairs: tuple[NewsPairEvidence, ...]


class NewsEnrichmentManifest(EnrichmentModel):
    schema_version: str = "news-enrichment-v1"
    decision_time: datetime
    computed_at: datetime
    reconstruction_policy: Literal["deterministic_reconstruction_v1"]
    query_mode: Literal["strict", "historical_research"]
    allow_historical_proxy: bool
    allow_retrospective_registry: bool
    temporal_status: Literal["strict_inputs", "historical_research_unverified"]
    input_fingerprint: str
    registry_fingerprint: str
    registry_version: str
    parameters_fingerprint: str
    parameters: NewsGroupingParameters
    eligible_revision_ids: tuple[str, ...]
    candidate_pairs: int
    warnings: tuple[str, ...]

    @field_validator("decision_time", "computed_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class NewsClusterSnapshot(EnrichmentModel):
    snapshot_id: str
    manifest: NewsEnrichmentManifest
    inputs: tuple[NewsRecord, ...]
    entity_links: tuple[NewsEntityLink, ...]
    duplicates: tuple[NewsDedupRecord, ...]
    event_clusters: tuple[NewsEventCluster, ...]
    pair_evidence: tuple[NewsPairEvidence, ...]

    def reproducible_payload(self) -> dict:
        """Exclude computation wall-clock time from deterministic identity."""
        payload = self.model_dump(mode="json", exclude={"snapshot_id"})
        payload["manifest"].pop("computed_at")
        return payload
