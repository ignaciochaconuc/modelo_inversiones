"""Immutable raw evidence and versioned Parquet storage for Phase 4A news."""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
from typing import Any

import pandas as pd

from investment_system.core.time_utils import ensure_utc
from investment_system.data.news_hashing import sha256_hex
from investment_system.data.schemas.news import (
    AvailableAtSource, NEWS_NORMALIZER_VERSION, NEWS_SCHEMA_VERSION,
    NewsQueryMode, NewsRecord, RawNewsItem, RawPayloadFormat,
)


class NewsStore:
    """Local store with content-addressed raw payloads and immutable revisions."""

    def __init__(
        self, raw_root: str | Path, processed_root: str | Path, *,
        schema_version: str = NEWS_SCHEMA_VERSION,
        normalizer_version: str = NEWS_NORMALIZER_VERSION,
    ) -> None:
        self.raw_root = Path(raw_root) / "news"
        self.capture_root = self.raw_root / "captures"
        self.payload_root = self.raw_root / "payloads"
        self.normalized_root = Path(processed_root) / "news" / schema_version
        self.normalized_path = self.normalized_root / "data.parquet"
        self.schema_version = schema_version
        self.normalizer_version = normalizer_version
        for path in (self.capture_root, self.payload_root, self.normalized_root):
            path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _atomic_bytes(path: Path, value: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_bytes(value)
        temporary.replace(path)

    @staticmethod
    def _atomic_json(path: Path, value: dict[str, Any]) -> None:
        encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, indent=2).encode("utf-8")
        NewsStore._atomic_bytes(path, encoded)

    @staticmethod
    def _atomic_parquet(frame: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp.parquet")
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)

    def payload_path(self, item: RawNewsItem) -> Path:
        suffix = ".json" if item.payload_format == RawPayloadFormat.CANONICAL_JSON else ".bin"
        return self.payload_root / item.provider / item.payload_hash[:2] / f"{item.payload_hash}{suffix}"

    def capture_path(self, item: RawNewsItem) -> Path:
        return self.capture_root / item.provider / f"{item.raw_capture_id}.json"

    def write_raw(self, item: RawNewsItem) -> bool:
        """Persist a raw capture safely; return whether the capture metadata was new."""
        payload_path = self.payload_path(item)
        if payload_path.exists():
            if payload_path.read_bytes() != item.raw_payload:
                raise ValueError(f"raw payload hash collision at {payload_path}")
        else:
            self._atomic_bytes(payload_path, item.raw_payload)
        capture_path = self.capture_path(item)
        metadata = item.model_dump(mode="json", exclude={"raw_payload"})
        metadata["payload_path"] = payload_path.relative_to(self.raw_root).as_posix()
        if capture_path.exists():
            existing = json.loads(capture_path.read_text(encoding="utf-8"))
            if existing != metadata:
                raise ValueError(f"raw capture identity collision at {capture_path}")
            return False
        self._atomic_json(capture_path, metadata)
        return True

    def read_raw_items(self, provider: str | None = None) -> list[RawNewsItem]:
        roots = [self.capture_root / provider] if provider else sorted(
            path for path in self.capture_root.iterdir() if path.is_dir()
        )
        items: list[RawNewsItem] = []
        for root in roots:
            if not root.exists():
                continue
            for capture_path in sorted(root.glob("*.json")):
                metadata = json.loads(capture_path.read_text(encoding="utf-8"))
                payload_path = self.raw_root / metadata.pop("payload_path")
                items.append(RawNewsItem.model_validate({**metadata, "raw_payload": payload_path.read_bytes()}))
        return items

    def read_records(self) -> list[NewsRecord]:
        if not self.normalized_path.exists():
            return []
        frame = pd.read_parquet(self.normalized_path)
        records: list[NewsRecord] = []
        for value in frame.to_dict("records"):
            cleaned = {
                key: (None if self._is_missing(item) else self._normalize_container(item))
                for key, item in value.items()
            }
            # Phase 4A.1 migrates legacy proxy rows in memory: publication was
            # never verified revision availability, so strict availability
            # becomes the real local first-seen timestamp.
            if cleaned.get("available_at_source") == AvailableAtSource.PUBLISHED_AT_PROXY.value:
                cleaned["historical_proxy_at"] = cleaned.get("available_at")
                cleaned["historical_proxy_source"] = AvailableAtSource.PUBLISHED_AT_PROXY.value
                cleaned["available_at"] = cleaned.get("first_seen_at")
                cleaned["available_at_source"] = AvailableAtSource.LOCAL_FIRST_SEEN.value
            cleaned.setdefault("historical_proxy_at", None)
            cleaned.setdefault("historical_proxy_source", None)
            records.append(NewsRecord.model_validate(cleaned))
        return records

    @staticmethod
    def _is_missing(value: object) -> bool:
        if isinstance(value, (list, tuple, dict)):
            return False
        result = pd.isna(value)
        return bool(result) if not hasattr(result, "__len__") else False

    @staticmethod
    def _normalize_container(value: object) -> object:
        if hasattr(value, "tolist") and not isinstance(value, (str, bytes)):
            return value.tolist()
        return value

    def write_records(self, records: list[NewsRecord]) -> int:
        """Add normalized revisions idempotently and preserve the earliest observation."""
        if not records:
            return 0
        existing = self.read_records()
        by_key: dict[tuple[str, str, str], NewsRecord] = {
            (record.revision_id, record.schema_version, record.normalizer_version): record
            for record in existing
        }
        inserted = 0
        for record in records:
            key = (record.revision_id, record.schema_version, record.normalizer_version)
            current = by_key.get(key)
            if current is None:
                by_key[key] = record
                inserted += 1
            elif (record.first_seen_at, record.ingested_at, record.raw_payload_hash) < (
                current.first_seen_at, current.ingested_at, current.raw_payload_hash,
            ):
                by_key[key] = record
        ordered = sorted(
            by_key.values(),
            key=lambda record: (
                record.provider, record.provider_news_id, record.available_at,
                record.revision_id, record.schema_version, record.normalizer_version,
            ),
        )
        self._write_record_frame(ordered)
        return inserted

    def replace_provider_records(self, provider: str, records: list[NewsRecord]) -> int:
        retained = [
            record for record in self.read_records()
            if not (
                record.provider == provider
                and record.schema_version == self.schema_version
                and record.normalizer_version == self.normalizer_version
            )
        ]
        combined = retained + records
        by_key = {
            (record.revision_id, record.schema_version, record.normalizer_version): record
            for record in sorted(combined, key=lambda item: (item.first_seen_at, item.raw_payload_hash), reverse=True)
        }
        ordered = sorted(
            by_key.values(),
            key=lambda record: (record.provider, record.provider_news_id, record.available_at, record.revision_id),
        )
        self._write_record_frame(ordered)
        return len(records)

    def _write_record_frame(self, records: list[NewsRecord]) -> None:
        frame = pd.DataFrame([record.model_dump(mode="python") for record in records])
        self._atomic_parquet(frame, self.normalized_path)

    def query_as_of(
        self,
        decision_time: datetime,
        *,
        mode: NewsQueryMode = NewsQueryMode.STRICT,
        allow_historical_proxy: bool = False,
        tickers: tuple[str, ...] | None = None,
        provider: str | None = None,
    ) -> list[NewsRecord]:
        """Return the latest eligible revision per logical provider article."""
        cutoff = ensure_utc(decision_time)
        if mode == NewsQueryMode.STRICT and allow_historical_proxy:
            raise ValueError("strict mode cannot enable published_at_proxy")
        wanted = {ticker.strip().upper() for ticker in tickers or () if ticker.strip()}
        eligible: list[tuple[NewsRecord, datetime]] = []
        for record in self.read_records():
            if record.schema_version != self.schema_version or record.normalizer_version != self.normalizer_version:
                continue
            if provider and record.provider != provider:
                continue
            effective_at = record.available_at
            if (
                mode == NewsQueryMode.HISTORICAL_RESEARCH
                and allow_historical_proxy
                and record.historical_proxy_at is not None
            ):
                effective_at = record.historical_proxy_at
            if effective_at <= cutoff:
                eligible.append((record, effective_at))
        eligible.sort(key=lambda item: (
            item[0].provider, item[0].provider_news_id, item[1],
            item[0].first_seen_at, item[0].published_at or item[1], item[0].revision_id,
        ))
        latest: dict[tuple[str, str], tuple[NewsRecord, datetime]] = {}
        for record, effective_at in eligible:
            latest[(record.provider, record.provider_news_id)] = (record, effective_at)
        selected = [
            item for item in latest.values()
            if not wanted or wanted.intersection(item[0].direct_tickers)
        ]
        selected.sort(key=lambda item: (
            item[1], item[0].provider, item[0].provider_news_id, item[0].revision_id,
        ))
        return [record for record, _ in selected]

    def audit_revisions(self, provider: str, provider_news_id: str) -> list[NewsRecord]:
        """Return all stored revisions for one logical article in deterministic order."""
        return sorted(
            (
                record for record in self.read_records()
                if record.provider == provider and record.provider_news_id == provider_news_id
            ),
            key=lambda record: (record.available_at, record.first_seen_at, record.revision_id),
        )

    def lineage(self, record: NewsRecord) -> dict[str, Any]:
        captures = [
            item for item in self.read_raw_items(record.provider)
            if item.payload_hash == record.raw_payload_hash
        ]
        if not captures:
            raise ValueError(f"missing raw lineage for revision {record.revision_id}")
        return {
            "record": record,
            "raw_payload": captures[0].raw_payload,
            "captures": captures,
        }

    def validate_integrity(self) -> dict[str, int]:
        raw_items = self.read_raw_items()
        records = self.read_records()
        payload_hashes = {item.payload_hash for item in raw_items}
        bad_raw_hashes = sum(sha256_hex(item.raw_payload) != item.payload_hash for item in raw_items)
        missing_lineage = sum(record.raw_payload_hash not in payload_hashes for record in records)
        keys = [(record.revision_id, record.schema_version, record.normalizer_version) for record in records]
        duplicate_records = len(keys) - len(set(keys))
        return {
            "raw_captures": len(raw_items),
            "raw_payloads": len(payload_hashes),
            "normalized_records": len(records),
            "logical_articles": len({(record.provider, record.provider_news_id) for record in records}),
            "bad_raw_hashes": bad_raw_hashes,
            "missing_lineage": missing_lineage,
            "duplicate_records": duplicate_records,
        }
