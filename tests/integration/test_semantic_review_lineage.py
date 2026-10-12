import json

from investment_system.audit.news_semantic_review import select_review_pairs
from investment_system.data.news_entities import fingerprint
from investment_system.data.news_evaluation import FIXTURE_TIME, fixture_registry
from investment_system.data.news_grouping import build_news_groups_as_of
from investment_system.data.news_hashing import canonical_json_bytes, raw_capture_id, sha256_hex
from investment_system.data.news_ingestion import NewsIngestionService
from investment_system.data.schemas.news import RawNewsItem
from investment_system.data.sources.finnhub_news import FinnhubNewsProvider
from investment_system.data.sources.news import NewsIngestionPolicy
from investment_system.data.storage.news_store import NewsStore


def test_review_keeps_original_revision_and_raw_lineage(tmp_path):
    store = NewsStore(tmp_path / "raw", tmp_path / "processed")
    items = []
    for identity in ("1", "2"):
        payload = canonical_json_bytes(dict(id=identity, headline="Apple quarterly earnings results with third quarter revenue information", related="AAPL", datetime=int(FIXTURE_TIME.timestamp())))
        digest = sha256_hex(payload)
        items.append(RawNewsItem(provider="finnhub", provider_news_id=identity, captured_at=FIXTURE_TIME,
            raw_payload=payload, payload_hash=digest, payload_format="canonical_json",
            raw_capture_id=raw_capture_id("finnhub", identity, digest, FIXTURE_TIME)))
    provider = FinnhubNewsProvider("synthetic-fixture-only")
    NewsIngestionService(provider, store, NewsIngestionPolicy()).ingest_items(items)
    provider.close()
    before = store.normalized_path.read_bytes()
    snapshot = build_news_groups_as_of(store, FIXTURE_TIME, fixture_registry(), reconstruction_policy="deterministic_reconstruction_v1")
    result = select_review_pairs(snapshot, size=1)
    for side in ("left", "right"):
        evidence = result["blind"]["cases"][0][side]
        record = next(record for record in store.read_records() if record.revision_id == evidence["revision_id"])
        assert store.lineage(record)["captures"][0].provider_news_id == evidence["provider_news_id"]
        assert store.lineage(record)["captures"][0].payload_hash == evidence["raw_payload_hash"]
    assert store.normalized_path.read_bytes() == before
