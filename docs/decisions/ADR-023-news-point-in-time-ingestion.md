# ADR-023: Versioned point-in-time news ingestion

## Status

Accepted for implementation; Phase 4A remains pending external review.

## Context

Financial news may be corrected after publication, returned by several ticker
queries and backfilled long after its economic date. Treating the latest text or
the provider publication timestamp as if it had been observed historically
would create look-ahead bias. Phase 4A must preserve evidence without performing
semantic deduplication, entity resolution, LLM interpretation or feature
construction.

## Decision

Implement the boundary `News Provider -> Raw Capture -> Normalization ->
Versioned News Store -> PIT Query` under `investment_system.data`.

`RawNewsItem` records provider identity, capture time, request context, payload
format, SHA-256 and deterministic capture identity. Exact transport bytes are
preferred. When an adapter receives an already decoded JSON object, it stores
canonical UTF-8 JSON with sorted keys, compact separators, Unicode preserved and
NaN forbidden, and declares `canonical_json`. Raw payloads are content-addressed
and immutable; capture metadata is stored separately.

`NewsRecord` uses `news-schema-v1` and `news-normalizer-v1`. `news_id` hashes
`provider + provider_news_id`. `content_hash` covers normalized provider content
but excludes schema, normalizer, ingestion and availability metadata.
`revision_id` hashes `news_id + content_hash`. Therefore provider content changes
create revisions, while a normalizer/schema change does not falsely claim a new
provider revision. The storage key also contains schema and normalizer versions.

All internal timestamps are timezone-aware UTC. `published_at` is the declared
publication time of the article; it is not evidence that a particular content
revision already existed. For live capture, revision `available_at =
max(published_at, first_seen_at)` when publication is present, and otherwise
equals `first_seen_at`. Historical backfills use a documented provider revision
timestamp only when explicitly supplied as `provider_revision_at`; otherwise
the revision remains available at local first-seen time.

An explicitly enabled historical approximation stores publication separately
as `historical_proxy_at` with source `published_at_proxy`. It never replaces the
verified/conservative revision `available_at`. The proxy communicates only that
the article was declared published by then, not that the downloaded revision
was available with the same content.

Strict PIT queries always enforce revision `available_at <= decision_time` and
reject naive decision timestamps. Historical research queries may use
`historical_proxy_at` only with a second explicit opt-in; returned records retain
the `published_at_proxy` marker so the approximation is not represented as
verified evidence.

Queries first apply temporal policy and cutoff, then deterministically select
the latest eligible revision per `provider + provider_news_id`, and only then
apply content filters such as ticker. Thus an obsolete ticker tag cannot revive
an earlier revision. `audit_revisions()` and raw lineage remain separate paths
for inspecting superseded content.

`direct_tickers` contains only explicit provider labels. Tickers used to query
the provider remain solely in each raw capture's `request_tickers`. Identical
payloads returned by several requests create one logical normalized revision
while preserving every original capture and request context; no entity
resolution is inferred.

Raw evidence lives under `data/raw/news`; normalized Parquet lives under
`data/processed/news/news-schema-v1`. No news record is connected to the
quantitative Feature Store. Finnhub `company-news` is the optional first adapter
because it exposes company-scoped news, provider IDs and publication timestamps.
Its API key is read from `FINNHUB_API_KEY`. Publication timestamps are not treated
as verified local availability, and historical coverage, plan entitlements and
retention/redistribution rights require external verification.

News configuration lives in `config/news.yaml`, deliberately outside the
Phase 3E snapshot config set. Phase 4A must not mutate the already-fingerprinted
`config/settings.yaml` or any frozen Phase 3 artifact.

## Consequences

The same provider article may have several immutable content revisions, while
exact reingestion is logically idempotent. Normalized data can be rebuilt from
raw captures without deleting raw evidence. Storage volume is higher and proxy
backfills are deliberately unavailable to strict backtests. Phase 4B remains
responsible for cross-source semantic deduplication and entity resolution;
Phase 4C and 4D remain responsible for interpretation and features.

Phase 4A.1 tightened these semantics after external review. Existing v1 rows
that encoded `published_at_proxy` directly as `available_at` are conservatively
migrated on read: strict availability becomes `first_seen_at` and the former
value is retained only as the explicit historical proxy.
