"""Phase 4A orchestration from provider capture to the versioned News Store."""
from __future__ import annotations

from dataclasses import dataclass

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
        records = [self.provider.normalize(item, self.policy) for item in items]
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
        records = [self.provider.normalize(item, self.policy) for item in items]
        self.store.replace_provider_records(self.provider.provider_name, records)
        return NewsIngestionSummary(
            provider=self.provider.provider_name,
            fetched_items=len(items),
            new_raw_captures=0,
            normalized_candidates=len(records),
            new_normalized_revisions=len(records),
        )

