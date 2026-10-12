from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from investment_system.data.news_evaluation import FIXTURE_TIME, fixture_registry, synthetic_record
from investment_system.data.news_grouping import build_news_groups_as_of
from investment_system.data.schemas.news import AvailableAtSource, NewsQueryMode
from investment_system.data.schemas.news_enrichment import NewsEntityRegistry, NewsGroupingParameters
from investment_system.data.storage.news_enrichment_store import NewsEnrichmentStore
from investment_system.data.storage.news_store import NewsStore


def build(store, cutoff=FIXTURE_TIME, registry=None, **kwargs):
    return build_news_groups_as_of(store, cutoff, registry or fixture_registry(),
        reconstruction_policy="deterministic_reconstruction_v1", **kwargs)


def populated(tmp_path):
    store = NewsStore(tmp_path / "raw", tmp_path / "processed")
    headline = "Apple announces quarterly earnings results and revenue for the third quarter"
    a, b = synthetic_record("a", headline), synthetic_record("b", headline)
    store.write_records([a, b])
    return store, a, b


def test_ids_order_idempotency_rebuild_and_original_conservation(tmp_path):
    store, a, b = populated(tmp_path)
    before = store.normalized_path.read_bytes()
    first = build(store)
    other = NewsStore(tmp_path / "other-raw", tmp_path / "other-processed")
    other.write_records([b, a])
    second = build(other, computed_at=FIXTURE_TIME + timedelta(days=100))
    assert first.snapshot_id == second.snapshot_id
    assert first.reproducible_payload() == second.reproducible_payload()
    assert len(first.duplicates) == 1 and first.duplicates[0].relationship == "exact_duplicate"
    enrichment = NewsEnrichmentStore(tmp_path / "processed")
    path = enrichment.write(first)
    committed = (path / "snapshot.json").read_bytes()
    enrichment.write(second)
    assert (path / "snapshot.json").read_bytes() == committed
    assert enrichment.read(first.snapshot_id).snapshot_id == first.snapshot_id
    assert enrichment.validate_integrity(store) == {"snapshots": 1}
    assert store.normalized_path.read_bytes() == before


def test_future_article_revision_and_registry_cannot_rewrite_past(tmp_path):
    store, a, b = populated(tmp_path)
    past = build(store)
    tomorrow = FIXTURE_TIME + timedelta(days=1)
    revised = synthetic_record("a", "Apple launches a different product release tomorrow", available_at=tomorrow)
    future = synthetic_record("future", a.headline, available_at=tomorrow)
    store.write_records([revised, future])
    entry = fixture_registry().entries[0].model_copy(update={"corporate_name": "Future Brand", "known_at": tomorrow})
    registry = fixture_registry().model_copy(update={"version": "future-release", "entries": (*fixture_registry().entries, entry)})
    rebuilt = build(store, registry=registry)
    assert past.snapshot_id == rebuilt.snapshot_id
    assert past.reproducible_payload() == rebuilt.reproducible_payload()
    after = build(store, tomorrow, registry=registry)
    assert revised.revision_id in after.manifest.eligible_revision_ids
    assert a.revision_id not in after.manifest.eligible_revision_ids
    assert future.revision_id not in past.manifest.eligible_revision_ids


def test_strict_registry_proxy_guards_and_research_markers(tmp_path):
    store = NewsStore(tmp_path / "raw", tmp_path / "processed")
    tomorrow = FIXTURE_TIME + timedelta(days=1)
    r = synthetic_record("late", "Apple announces quarterly earnings results and revenue for third quarter", available_at=tomorrow)
    r = r.model_copy(update={"historical_proxy_at": FIXTURE_TIME, "historical_proxy_source": AvailableAtSource.PUBLISHED_AT_PROXY})
    store.write_records([r])
    assert not build(store).inputs
    with pytest.raises(ValueError, match="strict"):
        build(store, allow_historical_proxy=True)
    with pytest.raises(ValueError, match="strict"):
        build(store, allow_retrospective_registry=True)
    research = build(store, mode=NewsQueryMode.HISTORICAL_RESEARCH, allow_historical_proxy=True)
    assert len(research.inputs) == 1
    assert research.manifest.temporal_status == "historical_research_unverified"
    assert all(link.temporal_status == "unverified_proxy" for link in research.entity_links)


def test_dst_equivalent_cutoffs_and_naive_rejection(tmp_path):
    store, _, _ = populated(tmp_path)
    for day in (datetime(2026, 3, 6, 20, 15, tzinfo=ZoneInfo("America/New_York")), datetime(2026, 3, 9, 20, 15, tzinfo=ZoneInfo("America/New_York"))):
        assert build(store, day).snapshot_id == build(store, day.astimezone(timezone.utc)).snapshot_id
    with pytest.raises(ValueError, match="timezone-aware"):
        build(store, datetime(2026, 1, 2))


def test_near_duplicates_and_shared_event_remain_distinct(tmp_path):
    store = NewsStore(tmp_path / "raw", tmp_path / "processed")
    a = synthetic_record("a", "Apple quarterly earnings results show revenue growth in the third quarter")
    b = synthetic_record("b", "Apple quarterly earnings results show revenue details in the third quarter")
    store.write_records([a, b])
    snapshot = build(store)
    assert not snapshot.duplicates
    assert len(snapshot.event_clusters) == 1
    assert snapshot.pair_evidence[0].relationship == "shared_event"


def test_balanced_sampling_is_deterministic_and_uses_only_eligible_inputs(tmp_path):
    store = NewsStore(tmp_path / "raw", tmp_path / "processed")
    records = [synthetic_record(str(index), f"Corporate update number {index} with enough headline text", ticker)
               for index, ticker in enumerate(("AAPL", "AAPL", "AAPL", "MSFT", "MSFT", "NVDA"))]
    store.write_records(list(reversed(records)))
    snapshot = build(store, max_articles=3, sample_strategy="provider_ticker_round_robin")
    assert sorted(record.direct_tickers[0] for record in snapshot.inputs) == ["AAPL", "MSFT", "NVDA"]
    future = synthetic_record("late", "Future corporate update with enough headline text", "JPM", available_at=FIXTURE_TIME + timedelta(days=1))
    store.write_records([future])
    assert snapshot.snapshot_id == build(store, max_articles=3, sample_strategy="provider_ticker_round_robin").snapshot_id


def test_lineage_through_real_phase4a_contracts(tmp_path):
    from investment_system.data.news_hashing import canonical_json_bytes, raw_capture_id, sha256_hex
    from investment_system.data.news_ingestion import NewsIngestionService
    from investment_system.data.schemas.news import RawNewsItem
    from investment_system.data.sources.finnhub_news import FinnhubNewsProvider
    from investment_system.data.sources.news import NewsIngestionPolicy
    store = NewsStore(tmp_path / "raw", tmp_path / "processed")
    payload = canonical_json_bytes(dict(id=1, headline="Apple corporate news", related="AAPL", datetime=int(FIXTURE_TIME.timestamp())))
    digest = sha256_hex(payload)
    raw = RawNewsItem(provider="finnhub", provider_news_id="1", captured_at=FIXTURE_TIME,
        raw_payload=payload, payload_format="canonical_json", payload_hash=digest,
        raw_capture_id=raw_capture_id("finnhub", "1", digest, FIXTURE_TIME))
    provider = FinnhubNewsProvider("synthetic-placeholder")
    NewsIngestionService(provider, store, NewsIngestionPolicy()).ingest_items([raw])
    provider.close()
    snapshot = build(store)
    enrichment = NewsEnrichmentStore(tmp_path / "processed")
    enrichment.write(snapshot)
    result = enrichment.lineage(snapshot.snapshot_id, snapshot.inputs[0].revision_id, store)
    assert result["news"]["captures"][0].raw_capture_id == raw.raw_capture_id
    assert result["clusters"] and result["entity_links"]
