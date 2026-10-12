"""Small synthetic labelled diagnostics, independent of predictive/holdout data."""
from __future__ import annotations

from collections import Counter
from datetime import date, datetime, timezone
import json
from pathlib import Path

from investment_system.data.news_entities import fingerprint, resolve_entities
from investment_system.data.news_grouping import classify_pair
from investment_system.data.news_hashing import logical_news_id, normalized_content_hash, revision_id
from investment_system.data.schemas.news import NewsRecord
from investment_system.data.schemas.news_enrichment import (
    EntityRegistryEntry, NewsEntityRegistry, NewsGroupingParameters,
)


FIXTURE_TIME = datetime(2026, 1, 2, 14, tzinfo=timezone.utc)


def synthetic_record(
    identity: str, headline: str, ticker: str = "AAPL", *,
    available_at: datetime = FIXTURE_TIME, published_at: datetime | None = FIXTURE_TIME,
    summary: str | None = None, url: str | None = None,
) -> NewsRecord:
    """Synthetic fixture; hashes use the unchanged Phase 4A content contract."""
    content = dict(
        headline=headline, summary=summary, content_ref=url, source_name="synthetic",
        source_url=url, language="en", direct_tickers=[ticker] if ticker else [],
        provider_entities=[], published_at=published_at, event_date=None,
    )
    news_id = logical_news_id("synthetic", identity)
    content_hash = normalized_content_hash(content)
    return NewsRecord(
        news_id=news_id, revision_id=revision_id(news_id, content_hash), provider="synthetic",
        provider_news_id=identity, **content, first_seen_at=available_at,
        available_at=available_at, available_at_source="local_first_seen", ingested_at=available_at,
        raw_payload_hash=fingerprint(content), content_hash=content_hash,
    )


def fixture_registry() -> NewsEntityRegistry:
    return NewsEntityRegistry(
        version="synthetic-registry-v1", universe_description="Synthetic evidence only; not a historical factual registry",
        entries=tuple(EntityRegistryEntry(
            entity_id=name.casefold(), corporate_name=name, security_id=ticker + "-fixture", ticker=ticker,
            effective_from=date(2000, 1, 1), known_at=datetime(2000, 1, 1, tzinfo=timezone.utc),
            evidence="Synthetic scenario authored for regression tests, not real corporate evidence",
        ) for ticker, name in (("AAPL", "Apple"), ("MSFT", "Microsoft"), ("NVDA", "Nvidia"))),
    )


def evaluate_entity_examples(path: str | Path = "tests/fixtures/news_entity_cases_v1.json") -> dict:
    dataset = json.loads(Path(path).read_text(encoding="utf-8"))
    base = fixture_registry()
    alphabet = tuple(base.entries[0].model_copy(update={
        "entity_id": "alphabet", "corporate_name": "Alphabet", "aliases": ("Google",),
        "ticker": ticker, "security_id": security,
    }) for ticker, security in (("GOOG", "alphabet-c"), ("GOOGL", "alphabet-a")))
    registry = base.model_copy(update={"entries": (*base.entries, *alphabet)})
    outcomes = []
    for case in dataset["cases"]:
        record = synthetic_record(case["id"], case["headline"], case["ticker"])
        links = resolve_entities(record, registry.entries, FIXTURE_TIME, FIXTURE_TIME, registry.version, "entity-resolver-v1")
        entities = sorted({link.entity_id for link in links if link.entity_id})
        ambiguous = any(link.status == "ambiguous_security" for link in links)
        outcomes.append({"id": case["id"], "predicted_entities": entities,
                         "expected_entities": case["expected_entities"],
                         "ambiguous_security": ambiguous,
                         "correct": entities == case["expected_entities"] and ambiguous == case["ambiguous_security"],
                         "rationale": case["rationale"]})
    return {"dataset_fingerprint": fingerprint(dataset), "provenance": dataset["provenance"],
            "cases": len(outcomes), "coverage": sum(bool(row["predicted_entities"]) for row in outcomes) / len(outcomes),
            "scenario_accuracy": sum(row["correct"] for row in outcomes) / len(outcomes),
            "abstentions": sum(not row["predicted_entities"] for row in outcomes),
            "security_ambiguities": sum(row["ambiguous_security"] for row in outcomes),
            "errors": [row for row in outcomes if not row["correct"]], "outcomes": outcomes,
            "limitations": ["Eight synthetic examples do not estimate real entity-link accuracy."]}


def evaluate_labelled_pairs(
    parameters: NewsGroupingParameters, path: str | Path = "tests/fixtures/news_pairs_v1.json",
    *, splits: tuple[str, ...] = ("development", "frozen_evaluation"),
) -> dict:
    dataset = json.loads(Path(path).read_text(encoding="utf-8"))
    outcomes = []
    registry = fixture_registry()
    for case in dataset["cases"]:
        if case["split"] not in splits:
            continue
        url = "https://synthetic.test/same" if case.get("same_url") else None
        left = synthetic_record(case["id"] + "-left", case["left"], case["left_ticker"], url=url)
        right = synthetic_record(case["id"] + "-right", case["right"], case["right_ticker"], url=url)
        entities = []
        for record in (left, right):
            links = resolve_entities(record, registry.entries, FIXTURE_TIME, FIXTURE_TIME, registry.version, parameters.resolver_version)
            entities.append({link.entity_id for link in links if link.entity_id})
        pair = classify_pair(left, right, tuple(sorted(entities[0] & entities[1])), FIXTURE_TIME, parameters)
        outcomes.append({"id": case["id"], "split": case["split"], "expected": case["label"],
                         "predicted": pair.relationship, "rationale": case["rationale"],
                         "similarity": pair.similarity, "headline_similarity": pair.headline_similarity})
    def scores(rows: list[dict], positive: set[str]) -> dict:
        tp = sum(row["expected"] in positive and row["predicted"] in positive for row in rows)
        fp = sum(row["expected"] not in positive and row["predicted"] in positive for row in rows)
        fn = sum(row["expected"] in positive and row["predicted"] not in positive for row in rows)
        precision = tp / (tp + fp) if tp + fp else None
        recall = tp / (tp + fn) if tp + fn else None
        f1 = 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None
        return dict(tp=tp, fp=fp, fn=fn, precision=precision, recall=recall, f1=f1)
    metrics = {}
    for split in splits:
        rows = [row for row in outcomes if row["split"] == split]
        metrics[split] = {
            "cases": len(rows), "duplicates": scores(rows, {"exact_duplicate", "editorial_duplicate"}),
            "same_event": scores(rows, {"exact_duplicate", "editorial_duplicate", "shared_event"}),
            "errors": [row for row in rows if row["expected"] != row["predicted"]],
        }
    return {"dataset_version": dataset["version"], "dataset_fingerprint": fingerprint(dataset),
            "provenance": dataset["provenance"], "metrics": metrics, "outcomes": outcomes,
            "limitations": ["Eight pairs per split; no reliable statistical precision/recall estimate.",
                            "Labels were authored before algorithm evaluation, require independent human adjudication.",
                            "Frozen synthetic evaluation is not the investment model TEST."]}
