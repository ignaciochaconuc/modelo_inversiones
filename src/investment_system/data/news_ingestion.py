"""Phase 4A orchestration from provider capture to the versioned News Store."""
from __future__ import annotations

from dataclasses import dataclass

from investment_system.data.news_hashing import raw_capture_id
from investment_system.data.schemas.news import NewsRecord, RawNewsItem
from investment_system.data.sources.news import NewsFetchRequest, NewsIngestionPolicy, NewsProvider
from investment_system.data.storage.news_store import NewsStore


@dataclass(frozen=True)
class NewsIngestionSummary:
    provider: str
    fetched_items: int
    new_raw_captures: int
    normalized_candidates: int
    new_normalized_revisions: int


class NewsIngestionService:
    def __init__(self, provider: NewsProvider, store: NewsStore, policy: NewsIngestionPolicy) -> None:
        self.provider = provider
        self.store = store
        self.policy = policy

    def ingest(self, request: NewsFetchRequest) -> NewsIngestionSummary:
        return self.ingest_items(self.provider.fetch_news(request))

    def ingest_items(self, items: list[RawNewsItem]) -> NewsIngestionSummary:
        if any(item.provider != self.provider.provider_name for item in items):
            raise ValueError("raw item provider does not match ingestion provider")
        new_raw = sum(self.store.write_raw(item) for item in items)
        grouped = self._merge_request_context(items)
        records = [self.provider.normalize(item, self.policy) for item in grouped]
        inserted = self.store.write_records(records)
        return NewsIngestionSummary(
            provider=self.provider.provider_name,
            fetched_items=len(items),
            new_raw_captures=new_raw,
            normalized_candidates=len(records),
            new_normalized_revisions=inserted,
        )

    def rebuild_from_raw(self) -> NewsIngestionSummary:
        items = self.store.read_raw_items(self.provider.provider_name)
        grouped = self._merge_request_context(items)
        records = [self.provider.normalize(item, self.policy) for item in grouped]
        self.store.replace_provider_records(self.provider.provider_name, records)
        return NewsIngestionSummary(
            provider=self.provider.provider_name,
            fetched_items=len(items),
            new_raw_captures=0,
            normalized_candidates=len(records),
            new_normalized_revisions=len(records),
        )

    @staticmethod
    def _merge_request_context(items: list[RawNewsItem]) -> list[RawNewsItem]:
        """Merge only byte-identical provider items returned for multiple symbols."""
        grouped: dict[tuple[str, str, str], RawNewsItem] = {}
        for item in sorted(items, key=lambda value: (value.captured_at, value.raw_capture_id)):
            key = (item.provider, item.provider_news_id, item.payload_hash)
            current = grouped.get(key)
            if current is None:
                grouped[key] = item
                continue
            tickers = tuple(sorted(set(current.request_tickers) | set(item.request_tickers)))
            if tickers != current.request_tickers:
                # The capture identity describes the original request. The merged
                # view is normalization-only and keeps the earliest capture ID.
                grouped[key] = RawNewsItem.model_validate({
                    **current.model_dump(mode="python"),
                    "request_tickers": tickers,
                    "raw_capture_id": raw_capture_id(
                        current.provider, current.provider_news_id, current.payload_hash,
                        current.captured_at, tickers,
                    ),
                })
        return list(grouped.values())
