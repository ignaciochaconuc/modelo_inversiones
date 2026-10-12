"""Audit local Phase 4A revisions and run controlled offline Phase 4B snapshots."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

import yaml

from investment_system.core.time_utils import ensure_utc
from investment_system.data.news_entities import load_entity_registry
from investment_system.data.news_evaluation import evaluate_entity_examples, evaluate_labelled_pairs
from investment_system.data.news_grouping import build_news_groups_as_of, load_grouping_parameters
from investment_system.data.schemas.news import NewsQueryMode
from investment_system.data.storage.news_enrichment_store import NewsEnrichmentStore
from investment_system.data.storage.news_store import NewsStore


def audit_revisions(records: list) -> dict:
    grouped = defaultdict(list)
    for record in records:
        grouped[(record.provider, record.provider_news_id)].append(record)
    fields = ("headline", "summary", "content_ref", "source_name", "source_url", "language",
              "direct_tickers", "provider_entities", "published_at", "event_date")
    changes = Counter()
    details = []
    for (provider, provider_id), revisions in sorted(grouped.items()):
        if len(revisions) < 2:
            continue
        changed = tuple(field for field in fields if len({str(getattr(record, field)) for record in revisions}) > 1)
        changes["|".join(changed)] += 1
        details.append({"provider": provider, "provider_news_id": provider_id,
                        "changed_fields": changed, "revision_ids": sorted(r.revision_id for r in revisions)})
    return {
        "normalized_records": len(records), "logical_articles": len(grouped),
        "additional_revision_rows": len(records) - len(grouped),
        "article_revision_count_distribution": dict(sorted(Counter(len(v) for v in grouped.values()).items())),
        "changed_field_combinations": dict(changes), "multi_revision_articles": details,
        "interpretation": "Additional rows are Phase 4A content-contract revisions, not independent editorial duplicate evidence.",
    }


def summary(snapshot) -> dict:
    resolved = {link.revision_id for link in snapshot.entity_links if link.entity_id}
    ambiguous = {link.revision_id for link in snapshot.entity_links if link.status.startswith("ambiguous")}
    return {
        "snapshot_id": snapshot.snapshot_id,
        "input_articles": len(snapshot.inputs),
        "exact_groups": sum(group.relationship == "exact_duplicate" for group in snapshot.duplicates),
        "editorial_near_groups": sum(group.relationship == "editorial_duplicate" for group in snapshot.duplicates),
        "event_clusters_including_singletons": len(snapshot.event_clusters),
        "multi_article_event_clusters": sum(len(cluster.members) > 1 for cluster in snapshot.event_clusters),
        "cluster_size_distribution": dict(sorted(Counter(len(cluster.members) for cluster in snapshot.event_clusters).items())),
        "articles_with_entity": len(resolved), "ambiguous_articles": len(ambiguous),
        "unresolved_articles": len(snapshot.inputs) - len(resolved),
        "entity_link_statuses": dict(Counter(link.status for link in snapshot.entity_links)),
        "candidate_pairs": snapshot.manifest.candidate_pairs,
        "accepted_pair_relationships": dict(Counter(pair.relationship for pair in snapshot.pair_evidence)),
        "input_fingerprint": snapshot.manifest.input_fingerprint,
        "registry_fingerprint": snapshot.manifest.registry_fingerprint,
        "parameters_fingerprint": snapshot.manifest.parameters_fingerprint,
        "warnings": snapshot.manifest.warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=datetime.fromisoformat)
    parser.add_argument("--max-articles", type=int, default=200)
    parser.add_argument("--raw-root", type=Path, default=Path("data/raw"))
    parser.add_argument("--processed-root", type=Path, default=Path("data/processed"))
    parser.add_argument("--report", type=Path, default=Path("data/reports/news/phase4b_pilot.json"))
    args = parser.parse_args()
    cutoff = ensure_utc(args.as_of or datetime.now(timezone.utc))
    store = NewsStore(args.raw_root, args.processed_root)
    registry = load_entity_registry()
    parameters = load_grouping_parameters()
    records = store.read_records()
    audit = audit_revisions(records)
    storage = NewsEnrichmentStore(args.processed_root)
    kwargs = dict(reconstruction_policy="deterministic_reconstruction_v1", max_articles=args.max_articles,
                  sample_strategy="provider_ticker_round_robin")
    strict = build_news_groups_as_of(store, cutoff, registry, parameters, **kwargs)
    destination = storage.write(strict)
    rebuilt = build_news_groups_as_of(store, cutoff, registry, parameters, **kwargs)
    storage.write(rebuilt)
    research = build_news_groups_as_of(
        store, cutoff, registry, parameters, mode=NewsQueryMode.HISTORICAL_RESEARCH,
        allow_retrospective_registry=True, **kwargs,
    )
    storage.write(research)
    universe = yaml.safe_load(Path("config/universe.yaml").read_text(encoding="utf-8"))
    registry_tickers = {entry.ticker for entry in registry.entries}
    labelled = evaluate_labelled_pairs(parameters)
    # Development-only comparison. Frozen evaluation never drives selection.
    development_comparisons = []
    for editorial in (0.90, 0.95):
        for event in (0.55, 0.65):
            candidate = parameters.model_copy(update={"editorial_threshold": editorial, "event_threshold": event})
            result = evaluate_labelled_pairs(candidate, splits=("development",))
            development_comparisons.append({"editorial": editorial, "event": event,
                                            "development_metrics": result["metrics"]["development"]})
    lineage_checked = 0
    raw_items = store.read_raw_items()
    raw_keys = {(item.provider, item.provider_news_id, item.payload_hash) for item in raw_items}
    for record in strict.inputs:
        if (record.provider, record.provider_news_id, record.raw_payload_hash) not in raw_keys:
            raise ValueError("missing raw capture lineage in pilot snapshot")
        lineage_checked += 1
    report = {
        "report_version": "phase4b-pilot-v1", "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "implemented_pending_external_review" if records else "partial_no_local_news",
        "provider": "local_finnhub_phase4a", "network_requests": 0, "decision_time": cutoff.isoformat(),
        "sample_policy": f"deterministic round-robin over first provider ticker (or unlabelled), at most {args.max_articles} latest eligible revisions",
        "sample_provider_ticker_distribution": dict(Counter(t for record in strict.inputs for t in record.direct_tickers)),
        "phase4a_audit": audit, "phase4a_integrity": store.validate_integrity(),
        "strict_snapshot": summary(strict), "research_snapshot": summary(research),
        "snapshot_location": str(destination), "enrichment_integrity": storage.validate_integrity(store),
        "lineage_checked_articles": lineage_checked, "rebuild_same_snapshot_id": strict.snapshot_id == rebuilt.snapshot_id,
        "registry_version": registry.version,
        "registry_universe_coverage": {"covered_tickers": sorted(registry_tickers & set(universe["tickers"])),
                                       "covered_count": len(registry_tickers & set(universe["tickers"])),
                                       "universe_count": len(universe["tickers"])},
        "labelled_diagnostics": labelled, "entity_labelled_diagnostics": evaluate_entity_examples(),
        "development_threshold_comparison": development_comparisons,
        "threshold_decision": "Keep configured conservative v1 thresholds; development comparisons only. No adjustment from frozen synthetic evaluation.",
        "real_pair_review": {
            "externally_reviewed_cases": 0, "agent_reviewed_cases": 2,
            "status": "pending_independent_adjudication",
            "cases": [
                {"provider_ids": ["142733043", "142736500"], "development_label": "different",
                 "rationale": "Omnibus market recap headline adds a new fact; high summary similarity alone cannot establish editorial equivalence or one event."},
                {"provider_ids": ["142706903", "142704791"], "development_label": "different",
                 "rationale": "Updated futures recap, multiple companies/topics; not reliable single-event or editorial duplicate evidence."},
            ],
            "review_context": "Two development negatives reviewed in the initial prefix sample (180 AAPL/20 MSFT); final pilot uses balanced round-robin sampling.",
        },
        "errors": [],
        "limitations": [
            "Registry is partial and locally curated; historical knowledge is not inferred from effective dates.",
            "Finnhub article labels vary by response; additional Phase 4A metadata revisions remain intact.",
            "Only headlines and summaries; independent event coverage with different wording may be missed.",
            "Synthetic labels require independent human review and cannot establish population accuracy.",
            "Locally captured October 2026 news was not historically observed on its publication date.",
            "Greedy complete-link partition is deterministic, not guaranteed globally optimal.",
            "No source content is copied into the public pilot report.",
        ],
    }
    NewsStore._atomic_json(args.report, report)
    print(json.dumps({"report": str(args.report), "status": report["status"], "audit": {
        key: audit[key] for key in ("normalized_records", "logical_articles", "additional_revision_rows")
    }, "strict": summary(strict)}, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
