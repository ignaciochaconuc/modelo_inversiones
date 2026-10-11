"""Deterministic identities and canonical JSON for Phase 4A news."""
from __future__ import annotations

from datetime import date, datetime
import hashlib
import json
from typing import Any


def _json_default(value: object) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    raise TypeError(f"unsupported canonical JSON value: {type(value).__name__}")


def canonical_json_bytes(value: Any) -> bytes:
    """Return UTF-8 JSON with sorted keys, compact separators and no NaN."""
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False, default=_json_default,
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def logical_news_id(provider: str, provider_news_id: str) -> str:
    return sha256_hex(f"news\x00{provider}\x00{provider_news_id}".encode("utf-8"))


def normalized_content_hash(content: dict[str, Any]) -> str:
    """Hash provider content only; schema/normalizer metadata is deliberately excluded."""
    return sha256_hex(canonical_json_bytes(content))


def revision_id(news_id: str, content_hash: str) -> str:
    return sha256_hex(f"revision\x00{news_id}\x00{content_hash}".encode("utf-8"))


def raw_capture_id(
    provider: str, provider_news_id: str, payload_hash: str,
    captured_at: datetime, request_tickers: tuple[str, ...] = (),
) -> str:
    tickers = tuple(sorted({ticker.strip().upper() for ticker in request_tickers if ticker.strip()}))
    identity = "\x00".join(
        (provider, provider_news_id, payload_hash, captured_at.isoformat(), ",".join(tickers))
    )
    return sha256_hex(identity.encode("utf-8"))
