"""Select evidence for independent human review, never supply reference labels."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations
import json
from pathlib import Path
from typing import Any

from investment_system.core.time_utils import ensure_utc
from investment_system.data.news_entities import fingerprint
from investment_system.data.news_grouping import EVENT_WORDS, anchors, classify_pair, tokens
from investment_system.data.schemas.news_enrichment import NewsClusterSnapshot


LABELS = ("exact_duplicate", "editorial_duplicate", "shared_event", "different", "uncertain")
CATEGORIES = (
    "high_similarity_rejected", "near_editorial_threshold", "near_event_threshold",
    "same_entity_nearby", "different_entities_similar_text", "earnings",
    "other_corporate_event", "factual_anchor_conflict", "ambiguous_entity", "random_eligible",
)
HUMAN_FIELDS = ("human_label", "human_rationale", "reviewer", "reviewed_at")
DEFAULT_LOCAL_ROOT = Path("data/reports/news/phase4b_semantic_review")


def case_id(left: str, right: str) -> str:
    return fingerprint(["semantic-case-v1", *sorted((left, right))])


def _evidence(record, include_summaries: bool) -> dict[str, Any]:
    fields = ("news_id", "revision_id", "provider", "provider_news_id", "published_at",
              "first_seen_at", "available_at", "available_at_source", "headline",
              "source_name", "source_url", "direct_tickers", "raw_payload_hash")
    value = record.model_dump(mode="json", include=set(fields))
    value["summary"] = record.summary if include_summaries else None
    return value


def select_review_pairs(
    snapshot: NewsClusterSnapshot, *, size: int = 36, seed: int = 42,
    include_summaries: bool = False, excluded_provider_pairs: tuple[tuple[str, str], ...] = (),
) -> dict[str, Any]:
    """Stratify a bounded PIT snapshot without assigning semantic ground truth.

    Pair scoring reuses the unchanged classifier. Additional cross-block pairs
    are marked audit-only; their scores are not claimed as stored pipeline output.
    """
    manifest = snapshot.manifest
    if manifest.query_mode != "strict" or manifest.allow_historical_proxy or manifest.allow_retrospective_registry:
        raise ValueError("semantic review requires a strict snapshot without proxy/registry opt-ins")
    if fingerprint(snapshot.reproducible_payload()) != snapshot.snapshot_id:
        raise ValueError("source snapshot fingerprint mismatch")
    if not 1 <= size <= 40:
        raise ValueError("review size must be between 1 and 40")
    if len(snapshot.inputs) > 500:
        raise ValueError("audit pair enumeration is limited to 500 snapshot articles")
    cutoff = manifest.decision_time
    if any(record.available_at > cutoff for record in snapshot.inputs):
        raise ValueError("future revision in strict source snapshot")
    if any(link.available_at > cutoff or link.temporal_status != "strict_inputs" for link in snapshot.entity_links):
        raise ValueError("noncausal entity evidence in source snapshot")
    identities = [(record.provider, record.provider_news_id) for record in snapshot.inputs]
    if len(identities) != len(set(identities)):
        raise ValueError("source snapshot contains multiple current revisions for a logical article")
    links = defaultdict(list)
    for link in snapshot.entity_links:
        links[link.revision_id].append(link)
    entities = {
        record.revision_id: {link.entity_id for link in links[record.revision_id]
                            if link.entity_id and link.status in {"resolved", "ambiguous_security"}}
        for record in snapshot.inputs
    }
    pipeline_pairs = {tuple(sorted((pair.left_revision_id, pair.right_revision_id))): pair
                      for pair in snapshot.pair_evidence}
    cluster_ids = {member: cluster.cluster_id for cluster in snapshot.event_clusters for member in cluster.members}
    dedup_ids = {member: group.group_id for group in snapshot.duplicates for member in group.members}
    excluded = {tuple(sorted(pair)) for pair in excluded_provider_pairs}
    pool = []
    omitted_prior = 0
    parameters = manifest.parameters
    records = sorted(snapshot.inputs, key=lambda record: record.revision_id)
    for left, right in combinations(records, 2):
        if tuple(sorted((left.provider_news_id, right.provider_news_id))) in excluded:
            omitted_prior += 1
            continue
        time_gap = abs(((left.published_at or left.available_at) - (right.published_at or right.available_at)).total_seconds()) / 3600
        if time_gap > parameters.max_hours:
            continue
        key = (left.revision_id, right.revision_id)
        common = tuple(sorted(entities[left.revision_id] & entities[right.revision_id]))
        availability = max([left.available_at, right.available_at] + [link.available_at for record in (left, right) for link in links[record.revision_id]])
        pair = pipeline_pairs.get(key) or classify_pair(left, right, common, availability, parameters)
        words_left = tokens(left.headline + " " + (left.summary or ""))
        words_right = tokens(right.headline + " " + (right.summary or ""))
        categories = []
        if pair.relationship == "different" and pair.similarity >= 0.85:
            categories.append("high_similarity_rejected")
        if abs(pair.similarity - parameters.editorial_threshold) <= 0.05:
            categories.append("near_editorial_threshold")
        if abs(pair.similarity - parameters.event_threshold) <= 0.05:
            categories.append("near_event_threshold")
        if common:
            categories.append("same_entity_nearby")
        if entities[left.revision_id] and entities[right.revision_id] and not common and pair.similarity >= 0.40:
            categories.append("different_entities_similar_text")
        if (set(words_left) & EVENT_WORDS["earnings"]) and (set(words_right) & EVENT_WORDS["earnings"]):
            categories.append("earnings")
        other_words = set().union(*(words for kind, words in EVENT_WORDS.items() if kind != "earnings"))
        if set(words_left) & other_words and set(words_right) & other_words:
            categories.append("other_corporate_event")
        # Surface numeric/date/action discrepancies are sampling cues, not human labels.
        _, numbers_left, actions_left = anchors(words_left)
        _, numbers_right, actions_right = anchors(words_right)
        if ((numbers_left and numbers_right and numbers_left != numbers_right)
                or (actions_left and actions_right and actions_left != actions_right)):
            categories.append("factual_anchor_conflict")
        if any(link.status.startswith("ambiguous") for record in (left, right) for link in links[record.revision_id]):
            categories.append("ambiguous_entity")
        identity = case_id(*key)
        pool.append({
            "case_id": identity, "left": _evidence(left, include_summaries),
            "right": _evidence(right, include_summaries), "sampling_categories": categories,
            "algorithm_pair_evidence": pair.model_dump(mode="json"),
            "prediction_origin": "stored_pipeline_pair" if key in pipeline_pairs else "audit_only_cross_block_score",
            "entity_links": {"left": [link.model_dump(mode="json") for link in links[left.revision_id]],
                             "right": [link.model_dump(mode="json") for link in links[right.revision_id]]},
            "same_event_cluster": cluster_ids[left.revision_id] == cluster_ids[right.revision_id],
            "same_duplicate_group": bool(dedup_ids.get(left.revision_id)) and dedup_ids.get(left.revision_id) == dedup_ids.get(right.revision_id),
        })
    random_order = sorted(pool, key=lambda row: fingerprint(["sampling-v1", seed, row["case_id"]]))
    for row in random_order[:min(8, len(pool))]:
        row["sampling_categories"].append("random_eligible")
    by_category = {}
    for category in CATEGORIES:
        candidates = [row for row in pool if category in row["sampling_categories"]]
        by_category[category] = sorted(candidates, key=lambda row: fingerprint([seed, category, row["case_id"]]))
    # Round-robin gives rare strata a chance; it never forces nonexistent quotas.
    selected = {}
    pointers = Counter()
    while len(selected) < min(size, len(pool)):
        progress = False
        for category in CATEGORIES:
            candidates = by_category[category]
            while pointers[category] < len(candidates):
                row = candidates[pointers[category]]
                pointers[category] += 1
                if row["case_id"] not in selected:
                    selected[row["case_id"]] = row
                    progress = True
                    break
            if len(selected) >= size:
                break
        if not progress:
            for row in random_order:
                if len(selected) >= size:
                    break
                selected.setdefault(row["case_id"], row)
            break
    rows = sorted(selected.values(), key=lambda row: fingerprint(["blind-order-v1", seed, row["case_id"]]))
    selection_fingerprint = fingerprint([row["case_id"] for row in rows])
    review_id = fingerprint(["semantic-review-v1", snapshot.snapshot_id, size, seed, include_summaries,
                             sorted(excluded), selection_fingerprint])
    blind = {"review_id": review_id, "allowed_labels": LABELS, "cases": [
        {"case_id": row["case_id"], "left": row["left"], "right": row["right"],
         **{field: "" for field in HUMAN_FIELDS}} for row in rows
    ]}
    technical = {"review_id": review_id, "source_snapshot_id": snapshot.snapshot_id,
                 "algorithm_version": parameters.algorithm_version,
                 "parameters": parameters.model_dump(mode="json"),
                 "input_fingerprint": manifest.input_fingerprint,
                 "registry_fingerprint": manifest.registry_fingerprint,
                 "parameters_fingerprint": manifest.parameters_fingerprint,
                 "cases": rows}
    evidence_fingerprint = fingerprint([{k: v for k, v in row.items() if k not in HUMAN_FIELDS} for row in blind["cases"]])
    metadata = {
        "review_id": review_id, "audit_version": "semantic-review-v1",
        "source_snapshot_id": snapshot.snapshot_id, "decision_time": cutoff.isoformat(),
        "seed": seed, "requested_pairs": size, "selected_pairs": len(rows),
        "eligible_pool_pairs": len(pool), "input_articles": len(records),
        "prior_development_pairs_excluded": omitted_prior,
        "category_pool_counts": {category: len(by_category[category]) for category in CATEGORIES},
        "category_selected_counts": {category: sum(category in row["sampling_categories"] for row in rows) for category in CATEGORIES},
        "categories_without_candidates": [category for category in CATEGORIES if not by_category[category]],
        "selection_fingerprint": selection_fingerprint, "blind_evidence_fingerprint": evidence_fingerprint,
        "technical_fingerprint": fingerprint(technical),
        "input_fingerprint": manifest.input_fingerprint, "registry_fingerprint": manifest.registry_fingerprint,
        "parameters_fingerprint": manifest.parameters_fingerprint,
        "include_summaries": include_summaries, "human_adjudication_status": "pending",
        "dataset_role": "independent_evaluation_pending_human_labels",
        "sampling_method": "deterministic hash-ranked strata round-robin plus seeded eligible-pair draw; overlapping categories",
        "limitations": [
            "Enriched difficult-case sample, not a probability estimate of population accuracy.",
            "Review covers one bounded snapshot and its publication-time window, not all local articles.",
            "Audit-only cross-block scores are distinguished from pipeline candidate/cluster membership.",
            "October 2026 local observation is not historical observation at publication time.",
            "Summaries omitted unless explicitly enabled after verifying local presentation rights.",
            "If cases guide algorithm changes, reclassify this set as development and obtain a new independent evaluation.",
        ],
    }
    return {"manifest": metadata, "blind": blind, "technical": technical}


def write_review_bundle(bundle: dict, destination: Path, *, allowed_root: Path = DEFAULT_LOCAL_ROOT) -> None:
    """Write only in the designated ignored local tree; never overwrite adjudication."""
    root, target = allowed_root.resolve(), destination.resolve()
    if not target.is_relative_to(root) or target == root:
        raise ValueError("restricted evidence destination must be a child of the ignored review root")
    marker = target / "manifest.json"
    if marker.exists():
        old = json.loads(marker.read_text(encoding="utf-8"))
        if old != bundle["manifest"]:
            raise ValueError("existing review differs; preserve it and choose another review identity")
        for name in ("blind", "technical"):
            if not (target / f"{name}.json").exists():
                raise ValueError("incomplete review bundle requires explicit recovery; human labels will not be overwritten")
        return
    target.mkdir(parents=True, exist_ok=True)
    if any((target / f"{name}.json").exists() for name in ("blind", "technical")):
        raise ValueError("refusing to overwrite an incomplete review")
    for name in ("blind", "technical", "manifest"):
        path = target / f"{name}.json"
        temporary = path.with_suffix(".tmp.json")
        temporary.write_text(json.dumps(bundle[name], ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8")
        temporary.replace(path)


def evaluate_adjudications(blind: dict, technical: dict, manifest: dict) -> dict:
    """Metrics require complete, attributed external adjudications; no inferred labels."""
    if not (blind["review_id"] == technical["review_id"] == manifest["review_id"]):
        raise ValueError("review identities do not match")
    if fingerprint(technical) != manifest["technical_fingerprint"]:
        raise ValueError("technical predictions were modified after sampling")
    rows = blind["cases"]
    identifiers = [row["case_id"] for row in rows]
    tech_ids = [row["case_id"] for row in technical["cases"]]
    if len(identifiers) != len(set(identifiers)) or set(identifiers) != set(tech_ids):
        raise ValueError("blind/technical case IDs differ or duplicate")
    ordered = {row["case_id"]: row for row in rows}
    immutable = [{k: v for k, v in ordered[identity].items() if k not in HUMAN_FIELDS} for identity in tech_ids]
    if fingerprint(immutable) != manifest["blind_evidence_fingerprint"]:
        raise ValueError("blind article evidence or original revision identities were changed")
    reviewed = []
    for row in rows:
        supplied_label = row.get("human_label", "")
        if not isinstance(supplied_label, str):
            raise ValueError("human_label must be an empty string or a permitted label")
        label = supplied_label.strip()
        if not label:
            continue
        if label not in LABELS:
            raise ValueError(f"invalid human label in case {row['case_id']}")
        if any(not isinstance(row.get(field), str) or not row[field].strip() for field in HUMAN_FIELDS[1:]):
            raise ValueError("adjudicated cases require rationale, reviewer and reviewed_at")
        ensure_utc(datetime.fromisoformat(row["reviewed_at"].replace("Z", "+00:00")))
        reviewed.append({**row, "human_label": label})
    result = {"review_id": manifest["review_id"], "cases": len(rows), "adjudicated": len(reviewed),
              "pending": len(rows) - len(reviewed), "metrics": None,
              "limitations": manifest["limitations"]}
    if not rows or len(reviewed) != len(rows):
        result["status"] = "human_adjudication_pending"
        return result
    if manifest["dataset_role"] != "independent_evaluation_pending_human_labels":
        raise ValueError("this set is not registered as an independent evaluation")
    predicted = {row["case_id"]: row for row in technical["cases"]}
    confusion = {label: {prediction: 0 for prediction in LABELS[:-1]} for label in LABELS}
    for row in reviewed:
        confusion[row["human_label"]][predicted[row["case_id"]]["algorithm_pair_evidence"]["relationship"]] += 1
    certain = [row for row in reviewed if row["human_label"] != "uncertain"]
    def binary(values: list[dict], positives: set[str], prediction_field: str | None = None) -> dict:
        tp = fp = fn = tn = 0
        errors = {"false_positive_case_ids": [], "false_negative_case_ids": []}
        for row in values:
            actual = row["human_label"] in positives
            tech = predicted[row["case_id"]]
            prediction = bool(tech[prediction_field]) if prediction_field else tech["algorithm_pair_evidence"]["relationship"] in positives
            tp += actual and prediction
            fp += not actual and prediction
            fn += actual and not prediction
            tn += not actual and not prediction
            if not actual and prediction:
                errors["false_positive_case_ids"].append(row["case_id"])
            if actual and not prediction:
                errors["false_negative_case_ids"].append(row["case_id"])
        return {"tp": tp, "fp": fp, "fn": fn, "tn": tn,
                "precision": tp / (tp + fp) if tp + fp else None,
                "recall": tp / (tp + fn) if tp + fn else None,
                "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else None, **errors}
    duplicate_labels = {"exact_duplicate", "editorial_duplicate"}
    event_labels = duplicate_labels | {"shared_event"}
    def metrics(values: list[dict]) -> dict:
        return {"certain_pairs": len(values), "pair_duplicate_detection": binary(values, duplicate_labels),
                "pair_same_event": binary(values, event_labels),
                "duplicate_group_membership": binary(values, duplicate_labels, "same_duplicate_group"),
                "event_cluster_membership": binary(values, event_labels, "same_event_cluster")}
    result.update(status="human_adjudication_completed", confusion_matrix=confusion,
                  uncertain_pairs=len(reviewed) - len(certain),
                  abstention_frequency=(len(reviewed) - len(certain)) / len(reviewed),
                  abstention_frequency_source="human_uncertain_label",
                  per_label_metrics={label: binary(certain, {label}) for label in LABELS[:-1]},
                  metrics=metrics(certain), by_sampling_category={category: metrics([
                      row for row in certain if category in predicted[row["case_id"]]["sampling_categories"]
                  ]) for category in CATEGORIES})
    return result
