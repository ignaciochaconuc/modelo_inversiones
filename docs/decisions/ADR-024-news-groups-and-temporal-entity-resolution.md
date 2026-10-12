# ADR-024: Deterministic news groups and temporal corporate identity

## Status

Accepted for implementation. Phase 4B is `implemented_pending_external_review`.

## Context

Phase 4A preserves provider articles and revisions. The local pilot contains
905 normalized revisions for 811 provider article IDs. All 84 multi-revision
articles differ only in provider ticker metadata (74 have two versions, ten
have three); the 94 extra rows are not evidence of editorial duplication.
Phase 4B must distinguish editorial reuse, independent event coverage and
corporate identity without changing those observations or interpreting returns.

## Decision

Implement `Normalized News Store -> Entity Resolution + Deduplication ->
Event Clustering -> PIT News Groups` in `investment_system.data`.
Versioned Pydantic contracts live in `data.schemas.news_enrichment`; outputs
include revision IDs, evidence, availability, parameters, versions and hashes.

### Temporal reconstruction

`build_news_groups_as_of()` requires an explicit
`deterministic_reconstruction_v1` policy. It normalizes the cutoff to UTC,
rejects naive timestamps, and obtains only the current eligible provider
revision through Phase 4A `query_as_of()`. Strict mode disallows publication
proxies and retrospective registry opt-in. It resolves identities using only
registry entries with `known_at <= decision_time`, then groups eligible news.
`computed_at` records actual computation, never historical observation.

Registry entries distinguish company, security/share class, ticker, aliases,
effective validity (exclusive end), local knowledge and source evidence. Alias
validity is evaluated at article publication date (availability when absent).
The curated registry is partial: current simple mappings are development
coverage with broad effective intervals, not complete historical identity
research. Its knowledge time is the local curation time on 2026-10-12; no
relationship is asserted to have been known locally in earlier decisions.
The fixed universe is coverage metadata, never a historical PIT universe.
Meta's name transition and FB/META symbol transition are separate dated entries;
GOOG and GOOGL map to one corporate entity but distinct securities.

Strict registry identity hashes the eligible entry set rather than the name of
a future registry release. Future entries and future news therefore cannot
alter an earlier snapshot. Historical research is a separate mode and records
unverified proxy/retrospective markers on links and manifest. Missing or
ambiguous entity resolution does not reject the underlying news record.

### Text, duplicate and event evidence

Text normalization uses Unicode NFKC, casefold and whole-word tokenization.
Numbers, dates and negation remain. Similarity is cosine over unigram and
adjacent-bigram count vectors. There is no fitted global vocabulary, embedding,
LLM or external interpretation request. Headline and optional summary are used;
Finnhub generally does not supply full article text.

Candidates come from inverted entity, identical normalized text and content-hash
blocks, restricted to a 48-hour publication/availability window. A configurable
100,000 candidate ceiling raises an explicit error instead of silently dropping
pairs. Large entity blocks can still be quadratic inside the time window;
controlled samples and narrower windows are required at larger scale.

An exact duplicate requires identical normalized headline/summary with enough
text and compatible factual/entity anchors. The Phase 4A content hash includes
metadata such as ticker tags and URL; it is not a universal editorial hash.
Canonical URLs remove known tracking parameters and fragments but keep other
query identity. Matching URL is supporting evidence only, never sufficient.

Editorial duplicates require cosine >= 0.90, headline cosine >= 0.65, common
resolved corporate identity and matching headline content after removing only
articles and `today`/`now`. A modified factual headline is not merged merely
because summaries are identical. Events require cosine >= 0.55, headline
cosine >= 0.65, common corporate identity and shared neutral event vocabulary.
Conflicting numbers, quarters, month anchors, product objects, explicit event
dates or legal/transaction stages block grouping. Multi-topic market roundups
are conservatively excluded from near/event grouping. These are lexical
compatibility checks, not sentiment, impact or market-direction scores.

Groups use a deterministic greedy complete-link partition: each new member
must pass the rule against every member already in the group. A~B and B~C do
not automatically imply A~C. The first eligible member in
available_at/news_id/revision_id order is representative. Duplicates and events
have separate contracts; event clusters include singleton articles so all
inputs remain represented.

### Entity evidence and ambiguity

Provider tags, explicit `$TICKER`/`NYSE:TICKER`/`NASDAQ:TICKER` notation and
whole-name aliases are distinct evidence. Request tickers never enter the
resolver. Bare T, V and C do not resolve by substring or token alone. A corporate
name with multiple share classes resolves the company and leaves the security
ambiguous. Unknown symbols and aliases yield explicit unresolved links. No
uncalibrated numeric confidence is provided. Brand/subsidiary aliases remain a
documented coarse corporate link, not an assertion that a subsidiary is the
same legal issuer.

### Reproducibility and storage

SHA-256 fingerprints cover ordered input records, eligible registry entries,
parameters and deterministic outputs. Snapshot identity excludes `computed_at`.
Membership-based group/cluster IDs are evidence identities, not permanent
economic event IDs. Legitimate later snapshots may have different IDs/members.

Outputs live under `data/processed/news_enrichment/news-enrichment-v1/<sha256>`.
Typed record JSON is stored in separate Parquet tables for inputs, links,
duplicates, clusters and pair evidence. A snapshot JSON commit is written last.
Single-writer atomic replacements follow the existing local store convention.
Rewriting an identical snapshot is a no-op; incomplete writes can be rebuilt.
Rebuild creates/reuses the fingerprint directory and preserves earlier
snapshots. Phase 4A files are never replaced or deduplicated. Lineage walks
cluster -> member -> entity links -> NewsRecord -> raw captures.

## Validation and limitations

`tests/fixtures/news_pairs_v1.json` contains 16 independently specified synthetic
semantic labels/rationales (eight development, eight frozen diagnostic pairs).
They were authored by the implementing agent before running the classifier,
not generated from classifier predictions; independent human adjudication is
pending. Development comparisons examine editorial 0.90/0.95 and event
0.55/0.65 only. The original conservative thresholds remain; frozen diagnostic
metrics do not select thresholds. Both splits miss one differently worded
same-event pair, which is reported as a false negative rather than optimized
away. The sample cannot support reliable population accuracy estimates.
Eight additional synthetic entity examples cover explicit names, provider tags,
multiple companies, whole-word boundaries, unknown symbols and Class A/C
ambiguity; their coverage/accuracy is a scenario diagnostic, not population
calibration. Historical identity transitions also have separate regression tests.

Two high-similarity real market recap pairs were qualitatively reviewed by the
agent using headlines; both are updated multi-topic stories and are treated as
development negatives. Only provider IDs and rationales are published. External
human review, broader multilingual/financial-event coverage, historical registry
coverage and systematic entity accuracy measurement remain pending.

This phase does not modify Phase 3 identities or datasets, construct predictive
features, invoke LLMs or start Phase 4C. News groups do not establish alpha or
portfolio profitability.
