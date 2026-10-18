# ADR-035: Opt-in synthetic runner diagnostic integration

## Status

Accepted for offline implementation only:
`nacho_evaluation_runner_p0_integrated_pending_authorization`.
No new inference authorized; Phase 4C.3 remains `not_started`.

## Decision

Extend ADR-033/034 with a separate evaluation overlay plus CLI opt-in. The
historical runtime profile stays byte-identical. A P0 overlay without the CLI
flag, or flag without overlay, is blocked. No production default changes.
The runtime settings, v3 wire, semantic validators, one-attempt policy and
budget reservations remain the same. Content TTL is 24 hours; sanitized
diagnostic metadata has its independent fixed 90-day policy.

P0 plans use runner v2 and bind the overlay and runtime hashes, diagnostic
version/policy/configuration, integration code and P0 source fingerprints.
Require `nacho-evaluation-authorization-v2`, including diagnostics_fingerprint,
an opaque new eval-UUID run ID and the exact plan/budget/freeze bindings.
Legacy v1 plans and authorization reading remain supported. Historical
authorization is neither upgraded nor reused.

Only the observed path uses interpret_observed. Preserve the delivery separately
while writing its sidecar: a failed independent write must not relabel an
already completed interpretation/rejection as not_run. Halt further calls,
retain ledger/attempt, report incomplete diagnostics, and never retry. A possible
call without a delivery is a technical failure requiring manual review, not a
proven no-call. Known no-call cases use the existing lifecycle contract.

Persist exclusive-create per-case bindings plus a closed metadata manifest
mapping all 32 cases to canonical sidecar IDs. Missing diagnostics are explicit
failures, not fabricated sidecars. Full audit requires every binding and checks
hashes, IDs, source/request/wire/cache/settings fingerprints and TTL, without
opening responses, attempts, exports or reference answers. Pin the manifest
SHA-256 outside the manifest; hashes are not digital signatures. An interrupted
manifest write remains a failed run; incremental bindings preserve evidence.

## Limits

Manifest and incremental bindings are restricted diagnostic metadata subject to
90-day access/cleanup policy, not public logs. Manifest lifetime begins at run
start; sidecars expire individually from their creation. Audit checks both.
No automatic physical purge, resume, backfill, new inference, comparison or
Phase 4C.3. Profile expiry remains enforced even in validate-only. Offline
fixtures are not evidence that provider prices/capabilities are currently valid.
