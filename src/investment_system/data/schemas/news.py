"""Versioned contracts for raw and normalized financial news."""
from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
import hashlib
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator

from investment_system.core.time_utils import ensure_utc
from investment_system.data.news_hashing import logical_news_id, normalized_content_hash, revision_id

NEWS_SCHEMA_VERSION = "news-schema-v1"
NEWS_NORMALIZER_VERSION = "news-normalizer-v1"


class RawPayloadFormat(StrEnum):
    """Whether raw bytes are transport-exact or canonicalized decoded JSON."""

    TRANSPORT_BYTES = "transport_bytes"
    CANONICAL_JSON = "canonical_json"


class AvailableAtSource(StrEnum):
    """Evidence used to establish when a news revision became available."""

    LOCAL_FIRST_SEEN = "local_first_seen"
    PROVIDER_TIMESTAMP = "provider_timestamp"
    PUBLISHED_AT_PROXY = "published_at_proxy"


class NewsQueryMode(StrEnum):
    STRICT = "strict"
    HISTORICAL_RESEARCH = "historical_research"


class RawNewsItem(BaseModel):
    """One immutable provider item captured before internal normalization.

    ``raw_payload`` contains exact transport bytes when ``payload_format`` is
    ``transport_bytes``. If an adapter can only expose a decoded JSON object,
    it must store canonical UTF-8 JSON and declare ``canonical_json``.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)
    provider: str = Field(min_length=1)
    provider_news_id: str = Field(min_length=1)
    captured_at: datetime
    raw_payload: bytes = Field(min_length=1, repr=False)
    payload_format: RawPayloadFormat
    payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    raw_capture_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_tickers: tuple[str, ...] = ()
    provider_revision_at: datetime | None = None
    request_metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_raw_identity(self) -> "RawNewsItem":
        captured_at = ensure_utc(self.captured_at)
        provider_revision_at = ensure_utc(self.provider_revision_at) if self.provider_revision_at else None
        tickers = tuple(sorted({ticker.strip().upper() for ticker in self.request_tickers if ticker.strip()}))
        expected_hash = hashlib.sha256(self.raw_payload).hexdigest()
        if self.payload_hash != expected_hash:
            raise ValueError("payload_hash does not match raw_payload")
        identity = "\x00".join(
            (self.provider, self.provider_news_id, self.payload_hash, captured_at.isoformat(), ",".join(tickers))
        ).encode("utf-8")
        if self.raw_capture_id != hashlib.sha256(identity).hexdigest():
            raise ValueError("raw_capture_id is not deterministic for this capture")
        object.__setattr__(self, "captured_at", captured_at)
        object.__setattr__(self, "provider_revision_at", provider_revision_at)
        object.__setattr__(self, "request_tickers", tickers)
        return self


class NewsRecord(BaseModel):
    """One normalized provider revision under ``news-schema-v1``."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    news_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    provider: str = Field(min_length=1)
    provider_news_id: str = Field(min_length=1)
    schema_version: str = NEWS_SCHEMA_VERSION
    normalizer_version: str = NEWS_NORMALIZER_VERSION
    headline: str = Field(min_length=1)
    summary: str | None = None
    content_ref: str | None = None
    source_name: str | None = None
    source_url: str | None = None
    language: str | None = None
    direct_tickers: tuple[str, ...] = ()
    provider_entities: tuple[str, ...] = ()
    published_at: datetime | None = None
    first_seen_at: datetime
    available_at: datetime
    available_at_source: AvailableAtSource
    historical_proxy_at: datetime | None = None
    historical_proxy_source: AvailableAtSource | None = None
    event_date: date | None = None
    ingested_at: datetime
    raw_payload_hash: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_hash: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_news_record(self) -> "NewsRecord":
        for name in ("first_seen_at", "available_at", "ingested_at"):
            object.__setattr__(self, name, ensure_utc(getattr(self, name)))
        if self.published_at is not None:
            object.__setattr__(self, "published_at", ensure_utc(self.published_at))
        if self.historical_proxy_at is not None:
            object.__setattr__(self, "historical_proxy_at", ensure_utc(self.historical_proxy_at))
        tickers = tuple(sorted({ticker.strip().upper() for ticker in self.direct_tickers if ticker.strip()}))
        entities = tuple(sorted({entity.strip() for entity in self.provider_entities if entity.strip()}))
        object.__setattr__(self, "direct_tickers", tickers)
        object.__setattr__(self, "provider_entities", entities)
        if self.available_at_source == AvailableAtSource.PUBLISHED_AT_PROXY:
            raise ValueError("published_at_proxy is not verified revision availability")
        if self.available_at_source == AvailableAtSource.LOCAL_FIRST_SEEN and self.available_at < self.first_seen_at:
            raise ValueError("local_first_seen availability cannot precede first_seen_at")
        if (self.historical_proxy_at is None) != (self.historical_proxy_source is None):
            raise ValueError("historical proxy timestamp and source must be set together")
        if self.historical_proxy_source is not None:
            if self.historical_proxy_source != AvailableAtSource.PUBLISHED_AT_PROXY:
                raise ValueError("historical_proxy_source must be published_at_proxy")
            if self.published_at is None or self.historical_proxy_at != self.published_at:
                raise ValueError("published_at_proxy must equal the declared article publication time")
        expected_news_id = logical_news_id(self.provider, self.provider_news_id)
        if self.news_id != expected_news_id:
            raise ValueError("news_id does not match provider identity")
        content = {
            "headline": self.headline,
            "summary": self.summary,
            "content_ref": self.content_ref,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "language": self.language,
            "direct_tickers": list(tickers),
            "provider_entities": list(entities),
            "published_at": self.published_at,
            "event_date": self.event_date,
        }
        expected_content_hash = normalized_content_hash(content)
        if self.content_hash != expected_content_hash:
            raise ValueError("content_hash does not match normalized provider content")
        if self.revision_id != revision_id(self.news_id, self.content_hash):
            raise ValueError("revision_id does not match news_id and content_hash")
        return self
