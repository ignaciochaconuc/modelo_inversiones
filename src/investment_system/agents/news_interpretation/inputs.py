"""Read-only PIT request construction, using existing 4A/4B contracts."""
from __future__ import annotations

from datetime import datetime

from investment_system.core.time_utils import ensure_utc
from investment_system.data.news_entities import eligible_registry_entries, fingerprint
from investment_system.data.schemas.news import NewsQueryMode
from investment_system.data.schemas.news_enrichment import NewsClusterSnapshot, NewsEntityRegistry
from investment_system.data.storage.news_store import NewsStore
from investment_system.agents.news_interpretation.schemas import (
    InterpretationTarget, NewsInterpretationRequest, SnapshotReference,
)


def build_interpretation_request(
    store: NewsStore, revision_id: str, decision_time: datetime, *,
    registry: NewsEntityRegistry | None = None,
    context_revision_ids: tuple[str, ...] = (),
    snapshot: NewsClusterSnapshot | None = None,
    target: InterpretationTarget | None = None,
    mode: NewsQueryMode = NewsQueryMode.STRICT,
    allow_historical_proxy: bool = False,
    allow_retrospective_registry: bool = False,
) -> NewsInterpretationRequest:
    """Choose current eligible revisions before any interpretation/context.

    No provider, retrieval or router calls. Optional computed 4B context is
    rejected in strict mode when generated after the requested decision.
    """
    cutoff = ensure_utc(decision_time)
    records = {r.revision_id: r for r in store.query_as_of(
        cutoff, mode=mode, allow_historical_proxy=allow_historical_proxy,
    )}
    required = (revision_id, *context_revision_ids)
    if any(identity not in records for identity in required):
        raise ValueError("requested revision is future, obsolete or missing at cutoff")
    primary = records[revision_id]
    fact_date = (primary.published_at or primary.available_at).date()
    entries = tuple(e for e in eligible_registry_entries(registry, cutoff, allow_retrospective_registry)
                    if e.effective_from <= fact_date and (e.effective_to is None or fact_date < e.effective_to)) if registry else ()
    reference = None
    if snapshot:
        if fingerprint(snapshot.reproducible_payload()) != snapshot.snapshot_id:
            raise ValueError("corrupt snapshot context")
        by_id = {r.revision_id: r for r in snapshot.inputs}
        if any(identity not in by_id or by_id[identity] != records[identity] for identity in required):
            raise ValueError("snapshot context does not contain identical requested revisions")
        reference = SnapshotReference(
            snapshot_id=snapshot.snapshot_id, decision_time=snapshot.manifest.decision_time,
            computed_at=snapshot.manifest.computed_at,
            available_at=max([snapshot.manifest.computed_at, *(r.available_at for r in snapshot.inputs),
                              *(link.available_at for link in snapshot.entity_links)]),
            registry_fingerprint=snapshot.manifest.registry_fingerprint,
            algorithm_version=snapshot.manifest.parameters.algorithm_version,
            temporal_status=snapshot.manifest.temporal_status,
            cluster_ids=tuple(c.cluster_id for c in snapshot.event_clusters if revision_id in c.members),
        )
    return NewsInterpretationRequest(
        news=primary, decision_time=cutoff, mode=mode,
        allow_historical_proxy=allow_historical_proxy,
        allow_retrospective_registry=allow_retrospective_registry,
        context_news=tuple(records[identity] for identity in sorted(context_revision_ids)),
        registry_entries=entries, snapshot=reference, target=target,
    )
