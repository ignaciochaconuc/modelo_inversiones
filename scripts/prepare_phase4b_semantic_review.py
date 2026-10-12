"""Prepare local blind evidence and frozen predictions; no provider requests."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from investment_system.audit.news_semantic_review import (
    DEFAULT_LOCAL_ROOT, select_review_pairs, write_review_bundle,
)
from investment_system.data.news_entities import fingerprint
from investment_system.data.news_entities import load_entity_registry
from investment_system.data.news_grouping import build_news_groups_as_of
from investment_system.data.storage.news_enrichment_store import NewsEnrichmentStore
from investment_system.data.storage.news_store import NewsStore


PUBLIC_SUMMARY_PATH = Path("data/reports/news/phase4b_semantic_review_summary.json")


def sanitized_summary(bundle: dict) -> dict:
    """Allow-list metadata: no article text, URLs, raw payloads or adjudications."""
    manifest = bundle["manifest"]
    allowed = (
        "review_id", "audit_version", "source_snapshot_id", "decision_time", "seed",
        "requested_pairs", "selected_pairs", "eligible_pool_pairs", "input_articles",
        "prior_development_pairs_excluded", "category_pool_counts", "category_selected_counts",
        "categories_without_candidates", "selection_fingerprint", "blind_evidence_fingerprint",
        "technical_fingerprint", "input_fingerprint", "registry_fingerprint", "parameters_fingerprint",
        "include_summaries", "human_adjudication_status", "dataset_role", "sampling_method", "limitations",
    )
    return {"report_version": "phase4b-semantic-review-summary-v1",
            "phase4b_status": "implemented_pending_external_review", "network_requests": 0,
            **{key: manifest[key] for key in allowed},
            "reproduction_command": "python scripts/prepare_phase4b_semantic_review.py --size 36 --seed 42"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot-id")
    parser.add_argument("--size", type=int, default=36)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--snapshot-articles", type=int, default=500,
                        help="bounded causal audit universe; unchanged 4B reconstruction, at most 500 articles")
    parser.add_argument("--include-summaries", action="store_true",
                        help="enable only after verifying provider permissions for local presentation")
    args = parser.parse_args()
    # Never load dotenv or credentials: audit has no provider dependency.
    pilot = json.loads(Path("data/reports/news/phase4b_pilot.json").read_text(encoding="utf-8"))
    snapshot_id = args.snapshot_id or pilot["strict_snapshot"]["snapshot_id"]
    storage = NewsEnrichmentStore("data/processed")
    snapshot = storage.read(snapshot_id)
    news = NewsStore("data/raw", "data/processed")
    if not 1 <= args.snapshot_articles <= 500:
        raise ValueError("snapshot-articles must be between 1 and 500")
    if args.snapshot_articles > len(snapshot.inputs):
        snapshot = build_news_groups_as_of(
            news, snapshot.manifest.decision_time, load_entity_registry(), snapshot.manifest.parameters,
            reconstruction_policy="deterministic_reconstruction_v1",
            max_articles=args.snapshot_articles, sample_strategy="provider_ticker_round_robin",
        )
        if snapshot.manifest.registry_fingerprint != storage.read(snapshot_id).manifest.registry_fingerprint:
            raise ValueError("registry evidence differs from the original reviewed Phase 4B snapshot")
    exclusions = tuple(tuple(row["provider_ids"]) for row in pilot.get("real_pair_review", {}).get("cases", []))
    bundle = select_review_pairs(snapshot, size=args.size, seed=args.seed,
                                 include_summaries=args.include_summaries,
                                 excluded_provider_pairs=exclusions)
    normalized = {record.revision_id: record for record in news.read_records()}
    raw_index = {}
    for item in news.read_raw_items():
        key = (item.provider, item.provider_news_id, item.payload_hash)
        raw_index.setdefault(key, []).append(item.raw_capture_id)
    for row in bundle["technical"]["cases"]:
        for side in ("left", "right"):
            evidence = row[side]
            record = normalized.get(evidence["revision_id"])
            if record is None or record.raw_payload_hash != evidence["raw_payload_hash"]:
                raise ValueError("review article is missing original normalized lineage")
            captures = raw_index.get((record.provider, record.provider_news_id, record.raw_payload_hash), [])
            if not captures:
                raise ValueError("review article is missing original raw capture lineage")
            row.setdefault("raw_capture_ids", {})[side] = sorted(captures)
    bundle["manifest"]["technical_fingerprint"] = fingerprint(bundle["technical"])
    bundle["manifest"]["lineage_verified_cases"] = len(bundle["technical"]["cases"])
    target = DEFAULT_LOCAL_ROOT / bundle["manifest"]["review_id"]
    bundle["manifest"]["base_snapshot_id"] = snapshot_id
    bundle["manifest"]["snapshot_article_limit"] = args.snapshot_articles
    write_review_bundle(bundle, target)
    source_file = target / "source_snapshot.json"
    if not source_file.exists():
        NewsStore._atomic_json(source_file, snapshot.model_dump(mode="json"))
    summary = sanitized_summary(bundle)
    summary["lineage_verified_cases"] = bundle["manifest"]["lineage_verified_cases"]
    summary["base_snapshot_id"] = snapshot_id
    summary["snapshot_article_limit"] = args.snapshot_articles
    command = f"python scripts/prepare_phase4b_semantic_review.py --snapshot-id {snapshot_id} --size {args.size} --seed {args.seed} --snapshot-articles {args.snapshot_articles}"
    summary["reproduction_command"] = command + (" --include-summaries" if args.include_summaries else "")
    NewsStore._atomic_json(PUBLIC_SUMMARY_PATH, summary)
    print(json.dumps({"review_id": bundle["manifest"]["review_id"], "pairs": bundle["manifest"]["selected_pairs"],
                      "local_directory": str(target), "summary": str(PUBLIC_SUMMARY_PATH),
                      "category_selected_counts": bundle["manifest"]["category_selected_counts"],
                      "categories_without_candidates": bundle["manifest"]["categories_without_candidates"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
