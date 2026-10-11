"""Provider-neutral news source contracts and normalization policy."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Protocol, runtime_checkable

from investment_system.data.schemas.news import NewsRecord, RawNewsItem


@dataclass(frozen=True)
class NewsFetchRequest:
    tickers: tuple[str, ...]
    start_date: date
    end_date: date

    def __post_init__(self) -> None:
        if self.start_date > self.end_date:
            raise ValueError("start_date must be <= end_date")
        normalized = tuple(dict.fromkeys(ticker.strip().upper() for ticker in self.tickers if ticker.strip()))
        if not normalized:
            raise ValueError("at least one ticker is required")
        object.__setattr__(self, "tickers", normalized)


@dataclass(frozen=True)
class NewsIngestionPolicy:
    """Availability policy; historical proxies are always explicit opt-in."""

    mode: str = "live"
    allow_published_at_proxy: bool = False

    def __post_init__(self) -> None:
        if self.mode not in {"live", "historical_backfill"}:
            raise ValueError("mode must be live or historical_backfill")
        if self.mode == "live" and self.allow_published_at_proxy:
            raise ValueError("published_at_proxy is only valid for historical_backfill")


@runtime_checkable
class NewsProvider(Protocol):
    """Adapter boundary: provider-specific fields do not escape normalization."""

    provider_name: str

    def fetch_news(self, request: NewsFetchRequest) -> list[RawNewsItem]: ...

    def normalize(self, item: RawNewsItem, policy: NewsIngestionPolicy) -> NewsRecord: ...

    def close(self) -> None: ...
