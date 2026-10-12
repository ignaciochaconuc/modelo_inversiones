"""Deterministic, conservative duplicate and event snapshots from PIT inputs."""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations
import math
from pathlib import Path
import re
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import yaml

from investment_system.core.time_utils import ensure_utc
from investment_system.data.news_entities import (
    eligible_registry_entries, fingerprint, resolve_entities,
)
from investment_system.data.schemas.news import NewsQueryMode, NewsRecord
from investment_system.data.schemas.news_enrichment import (
    NewsClusterSnapshot, NewsDedupRecord, NewsEnrichmentManifest, NewsEntityRegistry,
    NewsEventCluster, NewsGroupingParameters, NewsPairEvidence,
)
from investment_system.data.storage.news_store import NewsStore


def load_grouping_parameters(path: str | Path = "config/news_grouping.yaml") -> NewsGroupingParameters:
    return NewsGroupingParameters.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def tokens(text: str) -> tuple[str, ...]:
    """NFKC, casefold, Unicode whole words; preserve numbers and negation."""
    return tuple(re.findall(r"\w+", unicodedata.normalize("NFKC", text).casefold()))


def cosine(left: tuple[str, ...], right: tuple[str, ...]) -> float:
    def vector(words: tuple[str, ...]) -> Counter:
        return Counter([*words, *(f"{a} {b}" for a, b in zip(words, words[1:]))])
    a, b = vector(left), vector(right)
    denominator = math.sqrt(sum(x * x for x in a.values()) * sum(x * x for x in b.values()))
    return sum(x * b.get(key, 0) for key, x in a.items()) / denominator if denominator else 0.0


def canonical_url(url: str | None) -> str | None:
    """Remove fragments and known tracking keys; retain identity-bearing query keys."""
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    query = sorted((key, value) for key, value in parse_qsl(parsed.query) if not (
        key.casefold().startswith("utm_") or key.casefold() in {"fbclid", "gclid"}
    ))
    return urlunsplit((parsed.scheme.lower(), parsed.netloc.lower(), parsed.path, urlencode(query), ""))


EVENT_WORDS = {
    "earnings": {"earnings", "results", "quarter", "quarterly", "revenue"},
    "acquisition": {"acquisition", "acquire", "acquires", "merger", "buyout"},
    "product": {"launch", "launches", "launched", "unveils", "release"},
    "legal": {"lawsuit", "court", "settlement", "sues", "filed", "settled"},
    "analyst": {"analyst", "upgrade", "downgrade", "coverage", "rating"},
    "dividend": {"dividend", "distribution", "buyback"},
}


def anchors(words: tuple[str, ...]) -> tuple[set[str], set[str], set[str]]:
    values = set(words)
    kinds = {kind for kind, vocabulary in EVENT_WORDS.items() if values & vocabulary}
    numbers = {word for word in values if re.fullmatch(r"\d+|q[1-4]|20\d\d", word)}
    if values & {"quarter", "quarterly"}:
        numbers |= values & {"first", "second", "third", "fourth"}
    numbers |= values & {"january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"}
    actions = values & {"filed", "settled", "announced", "completed", "approved", "rejected", "not", "never", "denies"}
    return kinds, numbers, actions


def classify_pair(
    left: NewsRecord, right: NewsRecord, common_entities: tuple[str, ...],
    available_at: datetime, parameters: NewsGroupingParameters,
) -> NewsPairEvidence:
    left_head, right_head = tokens(left.headline), tokens(right.headline)
    a = tokens(left.headline + " " + (left.summary or ""))
    b = tokens(right.headline + " " + (right.summary or ""))
    similarity, head_similarity = cosine(a, b), cosine(left_head, right_head)
    hours = abs(((left.published_at or left.available_at) - (right.published_at or right.available_at)).total_seconds()) / 3600
    kinds_a, numbers_a, actions_a = anchors(a)
    kinds_b, numbers_b, actions_b = anchors(b)
    # Different named product/transaction objects are not one event merely
    # because the surrounding release boilerplate is similar.
    def objects(words: tuple[str, ...]) -> set[str]:
        vocabulary = {"iphone", "ipad", "watch", "tablet", "phone", "processor", "gpu"}
        return set(words) & vocabulary
    objects_a, objects_b = objects(a), objects(b)
    reasons = []
    relationship = "different"
    headline_core_a = tuple(word for word in left_head if word not in {"a", "an", "the", "today", "now"})
    headline_core_b = tuple(word for word in right_head if word not in {"a", "an", "the", "today", "now"})
    roundup = any(
        {"dow", "jones"}.issubset(set(head)) or "roundup" in head
        or {"stocks", "watch"}.issubset(set(head))
        for head in (left_head, right_head)
    )
    conflict = (
        (bool(kinds_a and kinds_b) and not (kinds_a & kinds_b))
        or (bool(numbers_a and numbers_b) and numbers_a != numbers_b)
        or (bool(actions_a or actions_b) and actions_a != actions_b)
        or (bool(objects_a and objects_b) and objects_a != objects_b)
        or (left.event_date is not None and right.event_date is not None and left.event_date != right.event_date)
        or (left.direct_tickers and right.direct_tickers and not set(left.direct_tickers).intersection(right.direct_tickers) and not common_entities)
    )
    if hours > parameters.max_hours:
        reasons.append("outside_time_window")
    elif conflict:
        reasons.append("incompatible_fact_anchors_or_entities")
    elif min(len(a), len(b)) < parameters.minimum_tokens:
        reasons.append("insufficient_text")
    elif a == b and left_head == right_head:
        relationship = "exact_duplicate"
        reasons.append("identical_normalized_headline_and_summary")
    elif common_entities and headline_core_a == headline_core_b and similarity >= parameters.editorial_threshold and head_similarity >= parameters.headline_threshold:
        relationship = "editorial_duplicate"
        reasons.append("high_text_similarity_with_entity_and_fact_compatibility")
    elif not roundup and common_entities and kinds_a & kinds_b and similarity >= parameters.event_threshold and head_similarity >= parameters.headline_threshold:
        relationship = "shared_event"
        reasons.append("shared_entity_event_vocabulary_and_compatible_fact_anchors")
    else:
        reasons.append("insufficient_event_or_editorial_evidence")
    if canonical_url(left.source_url) and canonical_url(left.source_url) == canonical_url(right.source_url):
        reasons.append("matching_url_support_only")
    return NewsPairEvidence(
        left_revision_id=left.revision_id, right_revision_id=right.revision_id,
        relationship=relationship, similarity=similarity, headline_similarity=head_similarity,
        hours_apart=hours, common_entities=common_entities, reasons=tuple(reasons), available_at=available_at,
    )


def complete_link_groups(ids: list[str], pairs: dict, accepted: set[str]) -> list[tuple[str, ...]]:
    """Deterministic greedy partition; a member must match every existing member."""
    groups: list[list[str]] = []
    for revision in ids:
        for group in groups:
            if all(
                tuple(sorted((revision, member))) in pairs
                and pairs[tuple(sorted((revision, member)))].relationship in accepted
                for member in group
            ):
                group.append(revision)
                break
        else:
            groups.append([revision])
    return [tuple(group) for group in groups]


def build_news_groups_as_of(
    store: NewsStore, decision_time: datetime, registry: NewsEntityRegistry,
    parameters: NewsGroupingParameters | None = None, *,
    reconstruction_policy: str,
    mode: NewsQueryMode = NewsQueryMode.STRICT,
    allow_historical_proxy: bool = False,
    allow_retrospective_registry: bool = False,
    max_articles: int | None = None,
    sample_strategy: str = "prefix",
    computed_at: datetime | None = None,
) -> NewsClusterSnapshot:
    """Reconstruct from eligible revisions; never assert historical observation."""
    cutoff = ensure_utc(decision_time)
    mode = NewsQueryMode(mode)
    if reconstruction_policy != "deterministic_reconstruction_v1":
        raise ValueError("explicit deterministic_reconstruction_v1 policy is required")
    if mode == NewsQueryMode.STRICT and (allow_historical_proxy or allow_retrospective_registry):
        raise ValueError("strict snapshots cannot enable proxies or retrospective registry")
    if max_articles is not None and max_articles <= 0:
        raise ValueError("max_articles must be positive")
    if sample_strategy not in {"prefix", "provider_ticker_round_robin"}:
        raise ValueError("unknown deterministic sampling strategy")
    parameters = parameters or NewsGroupingParameters()
    records = store.query_as_of(cutoff, mode=mode, allow_historical_proxy=allow_historical_proxy)
    records = sorted(records, key=lambda record: (record.available_at, record.news_id, record.revision_id))
    if max_articles:
        if sample_strategy == "prefix":
            records = records[:max_articles]
        else:
            buckets: dict[str, list[NewsRecord]] = defaultdict(list)
            for record in records:
                buckets[record.direct_tickers[0] if record.direct_tickers else "_unlabelled"].append(record)
            selected = []
            index = 0
            while len(selected) < min(max_articles, len(records)):
                for key in sorted(buckets):
                    if index < len(buckets[key]) and len(selected) < max_articles:
                        selected.append(buckets[key][index])
                index += 1
            records = sorted(selected, key=lambda record: (record.available_at, record.news_id, record.revision_id))
    entries = eligible_registry_entries(registry, cutoff, allow_retrospective_registry)
    registry_fingerprint = fingerprint([entry.model_dump(mode="json") for entry in entries])
    # A future global registry release cannot rename an earlier causal entry set.
    registry_as_of_version = "registry-asof-v1:" + registry_fingerprint
    effective = {
        record.revision_id: (
            record.historical_proxy_at if allow_historical_proxy and record.historical_proxy_at else record.available_at
        ) for record in records
    }
    links = [link for record in records for link in resolve_entities(
        record, entries, cutoff, effective[record.revision_id], registry_as_of_version, parameters.resolver_version,
    )]
    entities: dict[str, set[str]] = defaultdict(set)
    link_availability = dict(effective)
    for link in links:
        if link.entity_id and link.status in {"resolved", "ambiguous_security"}:
            entities[link.revision_id].add(link.entity_id)
        link_availability[link.revision_id] = max(link_availability[link.revision_id], link.available_at)
    by_id = {record.revision_id: record for record in records}
    # Inverted blocks avoid a global cross product: entity, exact text, exact hash.
    blocks: dict[str, list[NewsRecord]] = defaultdict(list)
    for record in records:
        keys = {"entity:" + entity for entity in entities[record.revision_id]}
        keys.add("text:" + fingerprint(tokens(record.headline + " " + (record.summary or ""))))
        keys.add("hash:" + record.content_hash)
        for key in sorted(keys):
            blocks[key].append(record)
    candidates = set()
    for values in blocks.values():
        values.sort(key=lambda record: (record.published_at or record.available_at, record.revision_id))
        for index, left in enumerate(values):
            for right in values[index + 1:]:
                hours = ((right.published_at or right.available_at) - (left.published_at or left.available_at)).total_seconds() / 3600
                if hours > parameters.max_hours:
                    break
                candidates.add(tuple(sorted((left.revision_id, right.revision_id))))
                if len(candidates) > parameters.max_candidates:
                    raise ValueError("candidate budget exceeded; narrow the requested sample")
    pairs = {}
    for left_id, right_id in sorted(candidates):
        pairs[(left_id, right_id)] = classify_pair(
            by_id[left_id], by_id[right_id], tuple(sorted(entities[left_id] & entities[right_id])),
            max(link_availability[left_id], link_availability[right_id]), parameters,
        )
    ids = [record.revision_id for record in records]
    def group_evidence(members: tuple[str, ...]) -> tuple[NewsPairEvidence, ...]:
        return tuple(pairs[tuple(sorted(pair))] for pair in combinations(members, 2))
    duplicates = []
    for members in complete_link_groups(ids, pairs, {"exact_duplicate", "editorial_duplicate"}):
        if len(members) < 2:
            continue
        evidence = group_evidence(members)
        relation = "exact_duplicate" if all(pair.relationship == "exact_duplicate" for pair in evidence) else "editorial_duplicate"
        duplicates.append(NewsDedupRecord(
            group_id=fingerprint([parameters.algorithm_version, relation, sorted(members)]),
            relationship=relation, members=members, representative_revision_id=members[0],
            available_at=max(link_availability[member] for member in members), evidence_pairs=evidence,
        ))
    clusters = []
    for members in complete_link_groups(ids, pairs, {"exact_duplicate", "editorial_duplicate", "shared_event"}):
        evidence = group_evidence(members)
        clusters.append(NewsEventCluster(
            cluster_id=fingerprint([parameters.algorithm_version, "event_membership", sorted(members)]),
            members=members, representative_revision_id=members[0],
            entity_ids=tuple(sorted(set().union(*(entities[member] for member in members)))),
            available_at=max(link_availability[member] for member in members), evidence_pairs=evidence,
        ))
    warnings = ["Retrospective deterministic reconstruction; computed_at is not historical observation."]
    if mode == NewsQueryMode.HISTORICAL_RESEARCH:
        warnings.append("Historical research; proxy/retrospective identities are not verified causal evidence.")
    manifest = NewsEnrichmentManifest(
        decision_time=cutoff, computed_at=computed_at or datetime.now(timezone.utc),
        reconstruction_policy=reconstruction_policy, query_mode=mode.value,
        allow_historical_proxy=allow_historical_proxy, allow_retrospective_registry=allow_retrospective_registry,
        temporal_status="strict_inputs" if mode == NewsQueryMode.STRICT else "historical_research_unverified",
        input_fingerprint=fingerprint([record.model_dump(mode="json") for record in records]),
        registry_fingerprint=registry_fingerprint,
        registry_version=registry_as_of_version, parameters_fingerprint=fingerprint(parameters.model_dump(mode="json")),
        parameters=parameters, eligible_revision_ids=tuple(ids), candidate_pairs=len(pairs), warnings=tuple(warnings),
    )
    snapshot = NewsClusterSnapshot(
        snapshot_id="pending", manifest=manifest, inputs=tuple(records), entity_links=tuple(links),
        duplicates=tuple(duplicates), event_clusters=tuple(clusters), pair_evidence=tuple(pairs.values()),
    )
    return snapshot.model_copy(update={"snapshot_id": fingerprint(snapshot.reproducible_payload())})
