"""Content-addressed Phase 4B snapshots; Phase 4A evidence stays untouched."""
from __future__ import annotations

import json
from pathlib import Path
import re

import pandas as pd

from investment_system.data.news_entities import fingerprint
from investment_system.data.schemas.news_enrichment import NewsClusterSnapshot
from investment_system.data.storage.news_store import NewsStore


class NewsEnrichmentStore:
    def __init__(self, processed_root: str | Path) -> None:
        self.root = Path(processed_root) / "news_enrichment" / "news-enrichment-v1"

    def snapshot_path(self, snapshot_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{64}", snapshot_id):
            raise ValueError("snapshot_id must be a SHA-256 hex digest")
        return self.root / snapshot_id

    def write(self, snapshot: NewsClusterSnapshot) -> Path:
        if fingerprint(snapshot.reproducible_payload()) != snapshot.snapshot_id:
            raise ValueError("snapshot fingerprint mismatch")
        destination = self.snapshot_path(snapshot.snapshot_id)
        final = destination / "snapshot.json"
        if final.exists():
            existing = self.read(snapshot.snapshot_id)
            if existing.reproducible_payload() != snapshot.reproducible_payload():
                raise ValueError("snapshot identity collision")
            return destination
        destination.mkdir(parents=True, exist_ok=True)
        # Manifest commit is last. Incomplete writes can be rebuilt idempotently.
        tables = {
            "inputs": snapshot.inputs, "entity_links": snapshot.entity_links,
            "duplicates": snapshot.duplicates, "clusters": snapshot.event_clusters,
            "pair_evidence": snapshot.pair_evidence,
        }
        for name, records in tables.items():
            frame = pd.DataFrame({"record_json": [record.model_dump_json() for record in records]})
            NewsStore._atomic_parquet(frame, destination / f"{name}.parquet")
        NewsStore._atomic_json(final, snapshot.model_dump(mode="json"))
        return destination

    def read(self, snapshot_id: str) -> NewsClusterSnapshot:
        path = self.snapshot_path(snapshot_id)
        snapshot = NewsClusterSnapshot.model_validate_json((path / "snapshot.json").read_text(encoding="utf-8"))
        if snapshot.snapshot_id != snapshot_id or fingerprint(snapshot.reproducible_payload()) != snapshot_id:
            raise ValueError("corrupt enrichment snapshot")
        for name, records in {
            "inputs": snapshot.inputs, "entity_links": snapshot.entity_links,
            "duplicates": snapshot.duplicates, "clusters": snapshot.event_clusters,
            "pair_evidence": snapshot.pair_evidence,
        }.items():
            values = pd.read_parquet(path / f"{name}.parquet")["record_json"].tolist()
            if [json.loads(value) for value in values] != [record.model_dump(mode="json") for record in records]:
                raise ValueError(f"corrupt snapshot table {name}")
        return snapshot

    def lineage(self, snapshot_id: str, revision_id: str, news_store: NewsStore) -> dict:
        snapshot = self.read(snapshot_id)
        record = next((record for record in snapshot.inputs if record.revision_id == revision_id), None)
        if record is None:
            raise KeyError(revision_id)
        return {
            "clusters": [cluster for cluster in snapshot.event_clusters if revision_id in cluster.members],
            "entity_links": [link for link in snapshot.entity_links if link.revision_id == revision_id],
            "news": news_store.lineage(record),
        }

    def validate_integrity(self, news_store: NewsStore) -> dict[str, int]:
        count = 0
        current = {(r.revision_id, r.raw_payload_hash) for r in news_store.read_records()}
        if self.root.exists():
            for path in sorted(self.root.glob("*/snapshot.json")):
                snapshot = self.read(path.parent.name)
                ids = {record.revision_id for record in snapshot.inputs}
                if any((record.revision_id, record.raw_payload_hash) not in current for record in snapshot.inputs):
                    raise ValueError("missing normalized snapshot lineage")
                if set(snapshot.manifest.eligible_revision_ids) != ids:
                    raise ValueError("manifest input membership mismatch")
                if any(link.revision_id not in ids for link in snapshot.entity_links):
                    raise ValueError("entity link references unknown revision")
                cluster_members = [member for cluster in snapshot.event_clusters for member in cluster.members]
                if len(cluster_members) != len(ids) or set(cluster_members) != ids:
                    raise ValueError("clusters must partition all input revisions")
                if snapshot.manifest.query_mode == "strict":
                    cutoff = snapshot.manifest.decision_time
                    if any(record.available_at > cutoff for record in snapshot.inputs):
                        raise ValueError("future strict snapshot input")
                    if any(link.available_at > cutoff or link.temporal_status != "strict_inputs" for link in snapshot.entity_links):
                        raise ValueError("noncausal strict entity link")
                count += 1
        return {"snapshots": count}
