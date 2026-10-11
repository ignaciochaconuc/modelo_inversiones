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

All internal timestamps are timezone-aware UTC. For live capture,
`available_at = max(published_at, first_seen_at)` when publication is present,
and otherwise equals `first_seen_at`. Historical backfills use an explicit
provider availability timestamp when supplied; otherwise they remain available
at local first-seen time. `published_at` may be used as a historical proxy only
through explicit configuration and is labeled `published_at_proxy`.

Strict PIT queries always enforce `available_at <= decision_time`, reject naive
decision timestamps, exclude publication proxies and deterministically select
the latest eligible revision per `provider + provider_news_id`. Historical
research queries include proxies only with a second explicit opt-in. Audit APIs
may return all captures/revisions and raw lineage.

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
