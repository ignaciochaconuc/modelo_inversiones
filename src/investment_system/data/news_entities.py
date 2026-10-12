"""Boundary-aware aliases and temporal entity/security registry selection."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
import unicodedata

import yaml

from investment_system.data.news_hashing import canonical_json_bytes, sha256_hex
from investment_system.data.schemas.news import NewsRecord
from investment_system.data.schemas.news_enrichment import (
    EntityRegistryEntry, NewsEntityLink, NewsEntityRegistry,
)


def fingerprint(value: object) -> str:
    return sha256_hex(canonical_json_bytes(value))


def load_entity_registry(path: str | Path = "config/news_entities.yaml") -> NewsEntityRegistry:
    return NewsEntityRegistry.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def eligible_registry_entries(
    registry: NewsEntityRegistry, cutoff: datetime, retrospective: bool,
) -> tuple[EntityRegistryEntry, ...]:
    return tuple(sorted(
        (entry for entry in registry.entries if retrospective or entry.known_at <= cutoff),
        key=lambda entry: (entry.entity_id, entry.security_id, entry.effective_from, entry.known_at),
    ))


def resolve_entities(
    record: NewsRecord, entries: tuple[EntityRegistryEntry, ...], cutoff: datetime,
    input_available_at: datetime, registry_version: str, resolver_version: str,
) -> list[NewsEntityLink]:
    """Resolve corporate names without claiming a unique share class from a name."""
    fact_date = (record.published_at or input_available_at).date()
    active = [entry for entry in entries if entry.effective_from <= fact_date and (
        entry.effective_to is None or fact_date < entry.effective_to
    )]
    text = unicodedata.normalize("NFKC", record.headline + " " + (record.summary or ""))
    matches: list[tuple[str, str, list[EntityRegistryEntry]]] = []
    for ticker in record.direct_tickers:
        matches.append(("provider_ticker", ticker, [entry for entry in active if entry.ticker == ticker]))
    # Plain T/V/C (or any other bare ticker) is not sufficient textual evidence.
    for token in sorted(set(re.findall(r"\$([A-Z][A-Z0-9.]{0,5})\b|(?:NYSE|NASDAQ):\s*([A-Z][A-Z0-9.]{0,5})\b", text))):
        ticker = next(value for value in token if value)
        matches.append(("explicit_ticker", ticker, [entry for entry in active if entry.ticker == ticker]))
    alias_map: dict[str, list[EntityRegistryEntry]] = {}
    for entry in active:
        for alias in (entry.corporate_name, *entry.aliases):
            alias_map.setdefault(alias, []).append(entry)
    for alias, candidates in sorted(alias_map.items()):
        if re.search(r"(?<!\w)" + re.escape(alias) + r"(?!\w)", text, flags=re.IGNORECASE):
            matches.append(("corporate_alias", alias, candidates))
    if not matches:
        matches.append(("unresolved", "no_explicit_entity_evidence", []))
    links = []
    for evidence_type, matched, candidates in matches:
        entities = sorted({entry.entity_id for entry in candidates})
        securities = sorted({entry.security_id for entry in candidates})
        if not entities:
            status, entity, security, ticker = "unresolved", None, None, None
        elif len(entities) > 1:
            status, entity, security, ticker = "ambiguous_entity", None, None, None
        elif len(securities) > 1:
            status, entity, security, ticker = "ambiguous_security", entities[0], None, None
        else:
            status, entity, security = "resolved", entities[0], securities[0]
            tickers = {entry.ticker for entry in candidates}
            ticker = next(iter(tickers)) if len(tickers) == 1 else None
        retrospective = any(entry.known_at > cutoff for entry in candidates)
        proxy = input_available_at != record.available_at
        temporal = "unverified_proxy" if proxy else ("retrospective_registry" if retrospective else "strict_inputs")
        availability = max([input_available_at] + [entry.known_at for entry in candidates if not retrospective])
        payload = dict(
            news_id=record.news_id, revision_id=record.revision_id, entity_id=entity,
            security_id=security, ticker=ticker, evidence_type=evidence_type,
            matched_text=matched, status=status, candidates=tuple(securities),
            registry_version=registry_version, resolver_version=resolver_version,
            available_at=availability, temporal_status=temporal,
            evidence=tuple(sorted({entry.evidence for entry in candidates})),
        )
        links.append(NewsEntityLink(link_id=fingerprint(payload), **payload))
    return sorted(links, key=lambda link: link.link_id)
