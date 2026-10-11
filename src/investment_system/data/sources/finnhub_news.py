"""Optional Finnhub company-news adapter for the reduced Phase 4A pilot."""
from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
import time
from typing import Any

import httpx

from investment_system.core.exceptions import DataSourceError, DataSourceRateLimitError
from investment_system.data.news_hashing import (
    canonical_json_bytes, logical_news_id, normalized_content_hash,
    raw_capture_id, revision_id, sha256_hex,
)
from investment_system.data.schemas.news import (
    AvailableAtSource, NEWS_NORMALIZER_VERSION, NEWS_SCHEMA_VERSION,
    NewsRecord, RawNewsItem, RawPayloadFormat,
)
from investment_system.data.sources.news import NewsFetchRequest, NewsIngestionPolicy


class FinnhubNewsProvider:
    """Normalize Finnhub ``company-news`` responses without retaining sentiment fields."""

    provider_name = "finnhub"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://finnhub.io/api/v1",
        timeout_seconds: float = 20,
        max_retries: int = 2,
        retry_backoff_seconds: float = 0.5,
        client: httpx.Client | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("FINNHUB_API_KEY is required")
        if max_retries < 0 or retry_backoff_seconds < 0:
            raise ValueError("retry settings must be non-negative")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._backoff = retry_backoff_seconds
        self._client = client or httpx.Client()
        self._owns_client = client is None
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def fetch_news(self, request: NewsFetchRequest) -> list[RawNewsItem]:
        captured: list[RawNewsItem] = []
        for ticker in request.tickers:
            response = self._request(
                "/company-news",
                {"symbol": ticker, "from": request.start_date.isoformat(), "to": request.end_date.isoformat()},
            )
            captured_at = self._clock()
            if captured_at.tzinfo is None:
                raise ValueError("news ingestion clock must return a timezone-aware datetime")
            try:
                payload = response.json()
            except ValueError as error:
                raise DataSourceError(f"Finnhub returned invalid JSON for {ticker}") from error
            if not isinstance(payload, list):
                raise DataSourceError(f"Finnhub returned an invalid company-news payload for {ticker}")
            for value in payload:
                if not isinstance(value, dict) or value.get("id") is None:
                    raise DataSourceError(f"Finnhub news item for {ticker} lacks a stable id")
                raw = canonical_json_bytes(value)
                payload_hash = sha256_hex(raw)
                tickers = (ticker,)
                captured.append(RawNewsItem(
                    provider=self.provider_name,
                    provider_news_id=str(value["id"]),
                    captured_at=captured_at,
                    raw_payload=raw,
                    payload_format=RawPayloadFormat.CANONICAL_JSON,
                    payload_hash=payload_hash,
                    raw_capture_id=raw_capture_id(
                        self.provider_name, str(value["id"]), payload_hash, captured_at, tickers,
                    ),
                    request_tickers=tickers,
                    request_metadata={
                        "endpoint": "company-news", "start_date": request.start_date.isoformat(),
                        "end_date": request.end_date.isoformat(),
                    },
                ))
        return captured

    def normalize(self, item: RawNewsItem, policy: NewsIngestionPolicy) -> NewsRecord:
        if item.provider != self.provider_name:
            raise ValueError("raw item belongs to a different provider")
        try:
            value = json.loads(item.raw_payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise DataSourceError("Finnhub raw item is not valid UTF-8 JSON") from error
        headline = str(value.get("headline") or "").strip()
        if not headline:
            raise DataSourceError(f"Finnhub news item {item.provider_news_id} has no headline")
        published_at = self._published_at(value.get("datetime"))
        related = tuple(
            sorted({part.strip().upper() for part in str(value.get("related") or "").split(",") if part.strip()})
        )
        # Request context is capture lineage, not provider evidence about content.
        direct_tickers = related
        content = {
            "headline": headline,
            "summary": self._optional(value.get("summary")),
            "content_ref": self._optional(value.get("url")),
            "source_name": self._optional(value.get("source")),
            "source_url": self._optional(value.get("url")),
            "language": None,
            "direct_tickers": list(direct_tickers),
            "provider_entities": [],
            "published_at": published_at,
            "event_date": None,
        }
        content_hash = normalized_content_hash(content)
        news_id = logical_news_id(item.provider, item.provider_news_id)
        available_at, available_source, proxy_at, proxy_source = self._availability(
            item, published_at, policy,
        )
        return NewsRecord(
            news_id=news_id,
            revision_id=revision_id(news_id, content_hash),
            provider=item.provider,
            provider_news_id=item.provider_news_id,
            schema_version=NEWS_SCHEMA_VERSION,
            normalizer_version=NEWS_NORMALIZER_VERSION,
            **content,
            first_seen_at=item.captured_at,
            available_at=available_at,
            available_at_source=available_source,
            historical_proxy_at=proxy_at,
            historical_proxy_source=proxy_source,
            ingested_at=item.captured_at,
            raw_payload_hash=item.payload_hash,
            content_hash=content_hash,
        )

    @staticmethod
    def _optional(value: object) -> str | None:
        result = str(value).strip() if value is not None else ""
        return result or None

    @staticmethod
    def _published_at(value: object) -> datetime | None:
        if value in (None, ""):
            return None
        try:
            return datetime.fromtimestamp(int(value), tz=timezone.utc)
        except (TypeError, ValueError, OSError) as error:
            raise DataSourceError(f"invalid Finnhub publication timestamp: {value!r}") from error

    @staticmethod
    def _availability(
        item: RawNewsItem, published_at: datetime | None, policy: NewsIngestionPolicy,
    ) -> tuple[datetime, AvailableAtSource, datetime | None, AvailableAtSource | None]:
        if policy.mode == "live":
            available_at = max(filter(None, (published_at, item.captured_at)))
            return available_at, AvailableAtSource.LOCAL_FIRST_SEEN, None, None
        proxy_at = published_at if policy.allow_published_at_proxy else None
        proxy_source = AvailableAtSource.PUBLISHED_AT_PROXY if proxy_at is not None else None
        if item.provider_revision_at is not None:
            return item.provider_revision_at, AvailableAtSource.PROVIDER_TIMESTAMP, proxy_at, proxy_source
        # A provider publication time describes the article, not an unknown
        # content revision. Local capture is the conservative revision evidence.
        return item.captured_at, AvailableAtSource.LOCAL_FIRST_SEEN, proxy_at, proxy_source

    def _request(self, path: str, params: dict[str, str]) -> httpx.Response:
        for attempt in range(self._max_retries + 1):
            try:
                response = self._client.get(
                    f"{self._base_url}{path}", params=params,
                    headers={"X-Finnhub-Token": self._api_key, "Accept": "application/json"},
                    timeout=self._timeout,
                )
            except httpx.HTTPError as error:
                if attempt == self._max_retries:
                    raise DataSourceError(f"Finnhub request failed: {type(error).__name__}") from error
                time.sleep(self._backoff * (2 ** attempt))
                continue
            if response.status_code == 429:
                if attempt == self._max_retries:
                    raise DataSourceRateLimitError("Finnhub news rate limit reached")
                time.sleep(self._backoff * (2 ** attempt))
                continue
            if response.is_error:
                raise DataSourceError(f"Finnhub news HTTP {response.status_code}")
            return response
        raise AssertionError("retry loop exhausted")

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "FinnhubNewsProvider":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
