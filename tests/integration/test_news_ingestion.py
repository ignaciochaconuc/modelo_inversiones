from datetime import datetime, timedelta, timezone

from investment_system.data.news_hashing import canonical_json_bytes, raw_capture_id, sha256_hex
from investment_system.data.news_ingestion import NewsIngestionService
from investment_system.data.schemas.news import NewsQueryMode, RawNewsItem, RawPayloadFormat
from investment_system.data.sources.finnhub_news import FinnhubNewsProvider
from investment_system.data.sources.news import NewsIngestionPolicy
from investment_system.data.sources.news import NewsFetchRequest
from investment_system.data.storage.news_store import NewsStore


def item(
    provider_id: int, headline: str, captured_at: datetime, *, published_at: datetime | None,
    related: str = "AAPL", request_tickers: tuple[str, ...] = ("AAPL",),
) -> RawNewsItem:
    payload = {
        "id": provider_id, "headline": headline, "summary": f"summary {headline}",
        "source": "Wire", "url": f"https://example.test/{provider_id}", "related": related,
    }
    if published_at is not None:
        payload["datetime"] = int(published_at.timestamp())
    raw = canonical_json_bytes(payload)
    digest = sha256_hex(raw)
    return RawNewsItem(
        provider="finnhub", provider_news_id=str(provider_id), captured_at=captured_at,
        raw_payload=raw, payload_format=RawPayloadFormat.CANONICAL_JSON,
        payload_hash=digest,
        raw_capture_id=raw_capture_id("finnhub", str(provider_id), digest, captured_at, request_tickers),
        request_tickers=request_tickers,
    )


def setup(tmp_path, policy: NewsIngestionPolicy | None = None):
    store = NewsStore(tmp_path / "raw", tmp_path / "processed")
    provider = FinnhubNewsProvider("secret")
    service = NewsIngestionService(provider, store, policy or NewsIngestionPolicy())
    return store, service


class SimulatedNewsProvider:
    """Deterministic provider used to exercise the provider-neutral boundary."""
    provider_name = "finnhub"

    def __init__(self, items: list[RawNewsItem]) -> None:
        self.items = items
        self.normalizer = FinnhubNewsProvider("fixture-secret")

    def fetch_news(self, request: NewsFetchRequest) -> list[RawNewsItem]:
        return list(self.items)

    def normalize(self, value: RawNewsItem, policy: NewsIngestionPolicy):
        return self.normalizer.normalize(value, policy)

    def close(self) -> None:
        self.normalizer.close()


def test_simulated_provider_exercises_provider_neutral_ingestion(tmp_path) -> None:
    seen = datetime(2026, 1, 2, 20, tzinfo=timezone.utc)
    provider = SimulatedNewsProvider([item(1, "fixture", seen, published_at=seen)])
    store = NewsStore(tmp_path / "raw", tmp_path / "processed")
    service = NewsIngestionService(provider, store, NewsIngestionPolicy())
    summary = service.ingest(NewsFetchRequest(("AAPL",), seen.date(), seen.date()))
    provider.close()
    assert summary.new_normalized_revisions == 1


def test_live_cutoff_uses_first_seen_not_publication(tmp_path) -> None:
    store, service = setup(tmp_path)
    cutoff = datetime(2026, 1, 2, 21, tzinfo=timezone.utc)
    published = cutoff - timedelta(hours=2)
    service.ingest_items([item(1, "late observation", cutoff + timedelta(minutes=1), published_at=published)])
    assert store.query_as_of(cutoff) == []
    service.ingest_items([item(2, "seen in time", cutoff - timedelta(minutes=1), published_at=published)])
    assert [record.provider_news_id for record in store.query_as_of(cutoff)] == ["2"]


def test_revision_after_cutoff_does_not_replace_prior_revision(tmp_path) -> None:
    store, service = setup(tmp_path)
    cutoff = datetime(2026, 1, 2, 21, tzinfo=timezone.utc)
    published = cutoff - timedelta(hours=1)
    first = item(1, "original", cutoff - timedelta(minutes=5), published_at=published)
    revised = item(1, "corrected", cutoff + timedelta(minutes=5), published_at=published)
    service.ingest_items([revised, first])
    records = store.read_records()
    assert len(records) == 2
    assert store.query_as_of(cutoff)[0].headline == "original"
    assert store.query_as_of(cutoff + timedelta(minutes=10))[0].headline == "corrected"


def test_identical_reingestion_is_idempotent_but_changed_content_is_revision(tmp_path) -> None:
    store, service = setup(tmp_path)
    seen = datetime(2026, 1, 2, 20, tzinfo=timezone.utc)
    original = item(1, "original", seen, published_at=seen - timedelta(hours=1))
    assert service.ingest_items([original]).new_normalized_revisions == 1
    assert service.ingest_items([original]).new_normalized_revisions == 0
    assert store.validate_integrity()["raw_captures"] == 1
    changed = item(1, "changed", seen + timedelta(minutes=1), published_at=seen - timedelta(hours=1))
    assert service.ingest_items([changed]).new_normalized_revisions == 1
    assert len(store.read_records()) == 2


def test_rebuild_from_raw_reproduces_records_and_lineage(tmp_path) -> None:
    store, service = setup(tmp_path)
    seen = datetime(2026, 1, 2, 20, tzinfo=timezone.utc)
    service.ingest_items([item(1, "one", seen, published_at=seen), item(2, "two", seen, published_at=None)])
    before = [(record.revision_id, record.raw_payload_hash) for record in store.read_records()]
    store.normalized_path.unlink()
    service.rebuild_from_raw()
    after = [(record.revision_id, record.raw_payload_hash) for record in store.read_records()]
    assert after == before
    lineage = store.lineage(store.read_records()[0])
    assert sha256_hex(lineage["raw_payload"]) == lineage["record"].raw_payload_hash


def test_proxy_is_excluded_from_strict_and_requires_explicit_research_opt_in(tmp_path) -> None:
    policy = NewsIngestionPolicy(mode="historical_backfill", allow_published_at_proxy=True)
    store, service = setup(tmp_path, policy)
    published = datetime(2021, 1, 2, 20, tzinfo=timezone.utc)
    captured = datetime(2026, 1, 2, 20, tzinfo=timezone.utc)
    service.ingest_items([item(1, "historical", captured, published_at=published)])
    cutoff = datetime(2022, 1, 2, tzinfo=timezone.utc)
    assert store.query_as_of(cutoff, mode=NewsQueryMode.STRICT) == []
    assert store.query_as_of(cutoff, mode=NewsQueryMode.HISTORICAL_RESEARCH) == []
    assert len(store.query_as_of(
        cutoff, mode=NewsQueryMode.HISTORICAL_RESEARCH, allow_historical_proxy=True,
    )) == 1


def test_missing_publication_is_conservatively_available_at_first_seen(tmp_path) -> None:
    store, service = setup(tmp_path, NewsIngestionPolicy(mode="historical_backfill"))
    seen = datetime(2026, 1, 2, 20, tzinfo=timezone.utc)
    service.ingest_items([item(1, "unknown publication", seen, published_at=None)])
    assert store.query_as_of(seen - timedelta(seconds=1)) == []
    assert store.query_as_of(seen)[0].available_at == seen


def test_query_is_order_independent_and_handles_ticker_shapes(tmp_path) -> None:
    seen = datetime(2026, 1, 2, 20, tzinfo=timezone.utc)
    values = [
        item(1, "no ticker", seen, published_at=seen, related="", request_tickers=()),
        item(2, "multi", seen, published_at=seen, related="MSFT,AAPL"),
    ]
    first_store, first_service = setup(tmp_path / "first")
    second_store, second_service = setup(tmp_path / "second")
    first_service.ingest_items(values)
    second_service.ingest_items(list(reversed(values)))
    first_ids = [record.revision_id for record in first_store.query_as_of(seen)]
    second_ids = [record.revision_id for record in second_store.query_as_of(seen)]
    assert first_ids == second_ids
    assert first_store.query_as_of(seen, tickers=("MSFT",))[0].direct_tickers == ("AAPL", "MSFT")
    assert first_store.validate_integrity() == {
        "raw_captures": 2, "raw_payloads": 2, "normalized_records": 2,
        "logical_articles": 2, "bad_raw_hashes": 0, "missing_lineage": 0,
        "duplicate_records": 0,
    }
