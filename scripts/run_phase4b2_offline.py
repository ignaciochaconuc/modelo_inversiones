"""Diagnose, compare and prepare disjoint blind evidence without network access."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path

from investment_system.audit.news_semantic_review import (
    evaluate_adjudications, select_review_pairs, write_review_bundle,
)
from investment_system.data.news_editorial_normalization import RULES, normalize_editorial_headline
from investment_system.data.news_entities import fingerprint, load_entity_registry
from investment_system.data.news_grouping import (
    anchors, build_news_groups_as_of, classify_pair, cosine, load_grouping_parameters, tokens,
)
from investment_system.data.schemas.news_enrichment import NewsClusterSnapshot
from investment_system.data.storage.news_enrichment_store import NewsEnrichmentStore
from investment_system.data.storage.news_store import NewsStore


LOCAL = Path("data/reports/news/phase4b2_local")
OLD_REVIEW = Path("data/reports/news/phase4b_semantic_review/8b446f52bcfcaac6f40541e7e9298db5371f60e68e584775fc4e6b492afe4ca0")
CASE = "3108bd96b8c21e06f7e4dec192021bce4a3a5aaf418580690696665d3eb66921"
PUBLIC = Path("data/reports/news/phase4b2_comparison.json")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def immutable_json(path: Path, value: dict) -> None:
    """Never overwrite evidence or adjudication on reruns."""
    if path.exists():
        if read_json(path) != value:
            raise ValueError(f"existing evidence differs: {path}")
    else:
        NewsStore._atomic_json(path, value)


def protected_hashes() -> dict[str, str]:
    """Original evidence/configuration, plus frozen Phase 3 artifacts."""
    roots = [Path(p) for p in (
        "data/reports/models", "data/raw/news", "data/processed/news",
        "data/processed/news_enrichment", "data/reports/news/phase4b_semantic_review",
        "data/features", "data/targets", "data/models", "config/models",
    )]
    files = {p for root in roots for p in root.rglob("*") if p.is_file()}
    files.update(Path(p) for p in (
        "config/settings.yaml", "config/universe.yaml", "config/provider_symbols.yaml",
        "config/corporate_action_overrides.yaml", "config/news.yaml", "config/news_entities.yaml",
        "config/news_grouping.yaml", "data/reports/news/phase4b_pilot.json",
        "data/reports/news/phase4b_semantic_review_summary.json",
    ))
    return {p.as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(files) if p.exists()}


def diagnose(source: NewsClusterSnapshot, technical: dict) -> dict:
    """Reproduce original rejection and headline-only normalization ablations."""
    row = next(row for row in technical["cases"] if row["case_id"] == CASE)
    ids = [row[side]["revision_id"] for side in ("left", "right")]
    left, right = [next(r for r in source.inputs if r.revision_id == identity) for identity in ids]
    stored = next(p for p in source.pair_evidence if {p.left_revision_id, p.right_revision_id} == set(ids))
    original = classify_pair(left, right, stored.common_entities, stored.available_at, source.manifest.parameters)
    if original != stored or row["prediction_origin"] != "stored_pipeline_pair":
        raise ValueError("original productive classification could not be reproduced")
    ablations = {}
    for name, rules in [("unchanged", ()), *((rule, (rule,)) for rule in RULES), ("all_rules", RULES)]:
        a, b = [tokens(normalize_editorial_headline(r.headline, rules)) for r in (left, right)]
        ablations[name] = {"headline_similarity": cosine(a, b), "headline_equal": a == b}
    return {
        "case_id": CASE, "source_snapshot_id": source.snapshot_id,
        "failure_class": "classification_failure", "candidate_in_pipeline": True,
        "classify_pair_called": True, "original_pair": original.model_dump(mode="json"),
        "entity_links": row["entity_links"], "headline_ablations": ablations,
        "anchors": [dict(zip(("kinds", "numbers", "actions"), map(sorted, anchors(tokens(r.headline + " " + (r.summary or "")))))) for r in (left, right)],
        "summary_characters": [len(r.summary or "") for r in (left, right)],
        "temporal_exclusion": False, "entity_resolution_failure": False,
        "failed_editorial_requirements": ["equal_headline_core", "global_cosine_at_least_0.90", "headline_cosine_at_least_0.65"],
        "shared_event_failure": ["no_common_event_kind", "headline_cosine_below_0.65"],
    }


def counts(snapshot: NewsClusterSnapshot) -> dict:
    return {
        "snapshot_id": snapshot.snapshot_id, "articles": len(snapshot.inputs),
        "candidate_pairs": snapshot.manifest.candidate_pairs,
        "pair_relationship_counts": dict(sorted(Counter(p.relationship for p in snapshot.pair_evidence).items())),
        "exact_groups": sum(g.relationship == "exact_duplicate" for g in snapshot.duplicates),
        "editorial_groups": sum(g.relationship == "editorial_duplicate" for g in snapshot.duplicates),
        "multinews_clusters": sum(len(c.members) > 1 for c in snapshot.event_clusters),
        "cluster_size_distribution": dict(sorted(Counter(str(len(c.members)) for c in snapshot.event_clusters).items())),
        "algorithm_version": snapshot.manifest.parameters.algorithm_version,
        "text_version": snapshot.manifest.parameters.text_version,
        "parameters_fingerprint": snapshot.manifest.parameters_fingerprint,
        "input_fingerprint": snapshot.manifest.input_fingerprint,
        "registry_fingerprint": snapshot.manifest.registry_fingerprint,
    }


def add_lineage(bundle: dict, news: NewsStore) -> None:
    captures = {}
    for item in news.read_raw_items():
        captures.setdefault((item.provider, item.provider_news_id, item.payload_hash), []).append(item.raw_capture_id)
    for row in bundle["technical"]["cases"]:
        row["raw_capture_ids"] = {}
        for side in ("left", "right"):
            evidence = row[side]
            ids = captures.get((evidence["provider"], evidence["provider_news_id"], evidence["raw_payload_hash"]), [])
            if not ids:
                raise ValueError("missing original raw capture")
            row["raw_capture_ids"][side] = sorted(ids)
    bundle["manifest"]["lineage_verified_cases"] = len(bundle["technical"]["cases"])
    bundle["manifest"]["technical_fingerprint"] = fingerprint(bundle["technical"])


def synthetic_blind(supplement: dict) -> dict:
    """Hide coverage cues as well as predictions from supplementary reviewers."""
    return {"dataset_role": supplement["dataset_role"], "provenance": supplement["provenance"],
            "cases": [{"case_id": r["case_id"], "left": r["left"], "right": r["right"],
                       "human_label": "", "human_rationale": "", "reviewer": "", "reviewed_at": ""}
                      for r in supplement["cases"]]}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnose-only", action="store_true")
    parser.add_argument("--evaluate-dir", type=Path)
    args = parser.parse_args()
    if args.evaluate_dir:
        target = args.evaluate_dir.resolve()
        if not target.is_relative_to((LOCAL / "reviews").resolve()):
            raise ValueError("evaluation must stay in the new ignored review tree")
        result = evaluate_adjudications(*(read_json(target / f"{name}.json") for name in ("blind", "technical", "manifest")))
        NewsStore._atomic_json(target / "evaluation.json", result)
        print(json.dumps({key: result[key] for key in ("status", "adjudicated", "pending")}))
        return 0
    before = protected_hashes()
    immutable_json(LOCAL / "protected_files.json", before)
    source = NewsClusterSnapshot.model_validate_json((OLD_REVIEW / "source_snapshot.json").read_text(encoding="utf-8"))
    technical = read_json(OLD_REVIEW / "technical.json")
    diagnosis = diagnose(source, technical)
    immutable_json(LOCAL / "initial_diagnosis.json", diagnosis)
    if args.diagnose_only:
        print(json.dumps({"case_id": CASE, "failure_class": diagnosis["failure_class"], "scores": diagnosis["original_pair"]}))
        return 0
    sidecar = {
        "prior_review_id": technical["review_id"], "dataset_role": "development_diagnostic",
        "case_ids": [r["case_id"] for r in technical["cases"]],
        "label_provenance": "user-reported ChatGPT-assisted adjudication; not independent human ground truth",
        "original_evidence_unchanged": True, "original_evaluation_fingerprint": fingerprint(read_json(OLD_REVIEW / "evaluation.json")),
        "uncertain_excluded_from_conclusive_metrics": True,
    }
    immutable_json(LOCAL / "prior_review_role.json", sidecar)
    news = NewsStore("data/raw", "data/processed")
    storage = NewsEnrichmentStore("data/processed")
    local_storage = NewsEnrichmentStore(LOCAL / "snapshots")
    pilot = read_json(Path("data/reports/news/phase4b_pilot.json"))
    old_pilot = storage.read(pilot["strict_snapshot"]["snapshot_id"])
    parameters = load_grouping_parameters("config/news_grouping_v1_1.yaml")
    comparisons = []
    new_source = None
    for old in (old_pilot, source):
        options = dict(reconstruction_policy="deterministic_reconstruction_v1",
                       max_articles=len(old.inputs), sample_strategy="provider_ticker_round_robin")
        rebuilt = build_news_groups_as_of(news, old.manifest.decision_time, load_entity_registry(), old.manifest.parameters, **options)
        if rebuilt.snapshot_id != old.snapshot_id:
            raise ValueError("original snapshot cannot be exactly reconstructed")
        new = build_news_groups_as_of(news, old.manifest.decision_time, load_entity_registry(), parameters, **options)
        if new.manifest.input_fingerprint != old.manifest.input_fingerprint or new.manifest.registry_fingerprint != old.manifest.registry_fingerprint:
            raise ValueError("comparison evidence changed")
        local_storage.write(new)
        new = local_storage.read(new.snapshot_id)
        old_pairs = {tuple(sorted((p.left_revision_id, p.right_revision_id))): p for p in old.pair_evidence}
        changed = [p for p in new.pair_evidence if p.relationship != old_pairs[tuple(sorted((p.left_revision_id, p.right_revision_id)))].relationship]
        immutable_json(LOCAL / "comparisons" / f"{len(old.inputs)}_changed_pairs.json", {
            "old_snapshot_id": old.snapshot_id, "new_snapshot_id": new.snapshot_id,
            "adjudication_status": "pending_external_review_possible_false_positives",
            "changed_pairs": [p.model_dump(mode="json") for p in changed],
        })
        comparisons.append({"old": counts(old), "new": counts(new), "changed_pairs": len(changed),
                            "old_identity_reproduced": True, "possible_new_false_positives": "pending_external_review"})
        new_source = new
    # Exclude every previously presented real pair, not merely the one FN.
    exclusions = {tuple(sorted((r["left"]["provider_news_id"], r["right"]["provider_news_id"])))
                  for p in Path("data/reports/news/phase4b_semantic_review").glob("*/blind.json")
                  for r in read_json(p)["cases"]}
    exclusions.update(tuple(sorted(r["provider_ids"])) for r in pilot.get("real_pair_review", {}).get("cases", []))
    bundle = select_review_pairs(new_source, size=40, seed=4202, excluded_provider_pairs=tuple(sorted(exclusions)),
                                 targeted_semantic_strata=True)
    if set(sidecar["case_ids"]) & {r["case_id"] for r in bundle["blind"]["cases"]}:
        raise ValueError("development/evaluation overlap")
    add_lineage(bundle, news)
    bundle["manifest"]["limitations"].append("All previous review pairs excluded; positive sampling cues are algorithm proposals, never reference labels.")
    root = LOCAL / "reviews"
    target = root / bundle["manifest"]["review_id"]
    write_review_bundle(bundle, target, allowed_root=root)
    immutable_json(target / "source_snapshot.json", new_source.model_dump(mode="json"))
    supplement = read_json(Path("tests/fixtures/news_semantic_evaluation_v1_1.json"))
    immutable_json(target / "synthetic_supplement_pending.json", supplement)
    # Do not recreate/overwrite external labels on reruns.
    synthetic_path = target / "synthetic_supplement_blind.json"
    if not synthetic_path.exists():
        immutable_json(synthetic_path, synthetic_blind(supplement))
    pending = evaluate_adjudications(bundle["blind"], bundle["technical"], bundle["manifest"])
    if not (target / "evaluation.json").exists():
        immutable_json(target / "evaluation.json", pending)
    integrity = local_storage.validate_integrity(news)
    if protected_hashes() != before:
        raise ValueError("protected evidence changed")
    summary = {
        "report_version": "phase4b2-comparison-v1", "phase4b_status": "implemented_pending_external_review",
        "network_requests": 0, "comparisons": comparisons,
        "protected_file_count": len(before), "protected_files_fingerprint": fingerprint(before),
        "protected_files_unchanged": True, "new_snapshot_integrity": integrity,
        "new_review_id": bundle["manifest"]["review_id"], "new_review_pairs": len(bundle["blind"]["cases"]),
        "review_status": "pending_external_review", "reference_metrics": None,
        "new_review_category_counts": bundle["manifest"]["category_selected_counts"],
        "new_review_categories_without_candidates": bundle["manifest"]["categories_without_candidates"],
        "excluded_prior_provider_pairs": len(exclusions), "evaluation_disjoint_from_prior_36": True,
        "synthetic_supplement_cases": len(supplement["cases"]),
        "synthetic_supplement_provenance": supplement["provenance"],
        "limitations": ["AI-assisted old adjudications are development, not human ground truth.",
                        "More groups does not imply higher quality; new memberships require external review.",
                        "Small enriched local evidence cannot estimate population precision/recall.",
                        "No justified change to shared-event vocabulary or candidate generation."],
    }
    immutable_json(PUBLIC, summary)
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
