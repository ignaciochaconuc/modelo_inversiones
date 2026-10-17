# ADR-034: Diagnostic metadata sidecars with independent retention

## Status

Accepted for P0 implementation only. No inference authorization, new evaluation,
ChatGPT comparison, prompt/semantic/attribution change or Phase 4C.3 initiation.
All historical records, including nacho-synthetic-20261014-run01, remain untouched.

## Reason and decision

The 24-hour content TTL correctly prevented later textual audit; aggregate
metadata could not identify exact branches per case. Do not extend content TTL.
Add opt-in `news-evaluation-diagnostics-v1`, independently stored under
`data/cache/news_evaluation_diagnostics`, not in attempt/result/replay DTOs.
Policy `diagnostic-metadata-retention-v1` is exactly 90 days from creation.

Allow only closed codes, safe structural paths, opaque IDs, hashes and UTC
timestamps. No source/model text, prompts, rationale, financial values, unknown
model-supplied IDs, exception bodies or credentials. Success/abstention/no-call
states remain distinct, without manufacturing attempt IDs for not_run.

Generate typed branch metadata at the original failing predicate. Numeric
ValueError subclasses preserve fixed messages and carry branch DTOs; Pydantic
adapters extract only those typed objects and sanitized structural locations,
not exception text. Stage/negation/resolver branches emit fixed DTOs directly.
Other existing closed-enum diagnostics may retain subcode not_available; do
not invent specificity. Specific subcodes are mandatory for instrumented rules
in new sidecars, paired with the appropriate pipeline stage.

A ContextVar collector observes the first validation of a new attempt only;
envelope verification/replay cannot create duplicate sidecars. Default calls
retain legacy serialization and write no metadata. Wire schemas, prompts,
predicates, old diagnostic DTOs and output versions remain unchanged. Source
bytes necessarily change for instrumentation, not historical record identities.

`interpret_observed` composes the already authorized one-attempt economic v3
service and separate store. Require new eval-UUID run IDs and a verified synthetic
source fingerprint. Cached, expired, pre-capture or mismatched deliveries cannot
backfill diagnostics. No changes to router, budgets, credentials or content TTL.
Existing evaluation CLI/profile are NOT silently opted in. Future integration
requires a new plan/code identity, explicit policy and separate authorization.

## Persistence, retention and risks

Immutable exclusive-create files per run+case bind record/attempt/request,
settings, wire and source fingerprints. Audit reads metadata only and enforces
created_at <= now < expires_at without opening attempts/cache/news/exports.
Expected sidecar IDs must be pinned in a future run manifest. Hashes are not
digital signatures against an attacker able to rewrite every artifact.

Fixed 90-day retention cannot be extended by rehashing expires_at. Original
content TTL remains unchanged. No automatic deletion is introduced: expired
metadata access is denied; physical cleanup requires separate authorization
and exact targets, never old attempts, references or ledgers. A longer policy
requires a new version, not retroactive modification.

Write failures propagate: future orchestration must halt and preserve any
already persisted attempt/ledger, with no inference retry. not_run may record
only explicit closed no-call lifecycle reasons; it cannot hide a possible call
whose persistence failed. This wrapper targets the current sequential workflow,
not a new concurrency scheduler.

Subcodes describe the guard, not semantic truth or negation scope. After content
TTL no quotation audit is possible. No retrospective diagnostics for old runs,
no Phase 4C.3, Feature Store or investment integration. See
[implementation and rollout](../phase4c2-p0-diagnostic-sidecars.md).
