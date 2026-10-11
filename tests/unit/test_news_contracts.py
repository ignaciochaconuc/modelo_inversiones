from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import httpx
import pytest
from pydantic import ValidationError

from investment_system.core.time_utils import ensure_utc
from investment_system.data.news_hashing import canonical_json_bytes, raw_capture_id, sha256_hex
from investment_system.data.schemas.news import NewsRecord, RawNewsItem, RawPayloadFormat
from investment_system.data.sources.finnhub_news import FinnhubNewsProvider
from investment_system.data.sources.news import NewsFetchRequest, NewsIngestionPolicy


def raw_item(payload: dict, captured_at: datetime, tickers: tuple[str, ...] = ("AAPL",)) -> RawNewsItem:
    raw = canonical_json_bytes(payload)
    digest = sha256_hex(raw)
    provider_id = str(payload["id"])
    return RawNewsItem(
        provider="finnhub", provider_news_id=provider_id, captured_at=captured_at,
        raw_payload=raw, payload_format=RawPayloadFormat.CANONICAL_JSON,
        payload_hash=digest,
        raw_capture_id=raw_capture_id("finnhub", provider_id, digest, captured_at, tickers),
        request_tickers=tickers,
    )


def test_canonical_json_and_raw_hashes_are_deterministic() -> None:
    assert canonical_json_bytes({"b": 2, "a": 1}) == canonical_json_bytes({"a": 1, "b": 2})
    captured = datetime(2026, 1, 2, tzinfo=timezone.utc)
    first = raw_item({"id": 1, "headline": "A"}, captured)
    second = raw_item({"headline": "A", "id": 1}, captured)
    assert first.payload_hash == second.payload_hash
    assert first.raw_capture_id == second.raw_capture_id


def test_raw_contract_rejects_naive_or_mismatched_hash() -> None:
    with pytest.raises(ValueError, match="timezone-aware"):
        raw_item({"id": 1}, datetime(2026, 1, 2))
    valid = raw_item({"id": 1}, datetime(2026, 1, 2, tzinfo=timezone.utc))
    with pytest.raises(ValidationError, match="payload_hash"):
        RawNewsItem.model_validate({**valid.model_dump(mode="python"), "payload_hash": "0" * 64})


def test_new_york_cutoff_converts_across_dst() -> None:
    ny = ZoneInfo("America/New_York")
    before = ensure_utc(datetime(2025, 3, 7, 20, 15, tzinfo=ny))
    after = ensure_utc(datetime(2025, 3, 10, 20, 15, tzinfo=ny))
    assert before.hour == 1  # EST: next day 01:15 UTC
    assert after.hour == 0   # EDT: next day 00:15 UTC


def test_finnhub_adapter_captures_canonical_items_and_encapsulates_fields() -> None:
    response_payload = [{
        "id": 7, "datetime": 1760000000, "headline": "Headline", "summary": "Summary",
        "related": "AAPL,MSFT", "source": "Wire", "url": "https://example.test/7",
        "sentiment": 0.9,
    }]
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json=response_payload))
    captured = datetime(2026, 1, 2, 20, tzinfo=timezone.utc)
    provider = FinnhubNewsProvider(
        "secret", client=httpx.Client(transport=transport), clock=lambda: captured,
    )
    items = provider.fetch_news(NewsFetchRequest(("AAPL",), captured.date(), captured.date()))
    record = provider.normalize(items[0], NewsIngestionPolicy(mode="live"))
    assert items[0].payload_format == RawPayloadFormat.CANONICAL_JSON
    assert record.direct_tickers == ("AAPL", "MSFT")
    assert record.language is None and not hasattr(record, "sentiment")
    assert record.available_at == max(record.published_at, captured)

    with pytest.raises(ValidationError, match="news_id"):
        NewsRecord.model_validate({**record.model_dump(mode="python"), "news_id": "0" * 64})


def test_finnhub_retries_are_limited() -> None:
    calls = 0
    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(429)
    provider = FinnhubNewsProvider(
        "secret", client=httpx.Client(transport=httpx.MockTransport(handler)),
        max_retries=2, retry_backoff_seconds=0,
    )
    with pytest.raises(Exception, match="rate limit"):
        provider.fetch_news(NewsFetchRequest(("AAPL",), datetime.now().date(), datetime.now().date()))
    assert calls == 3
