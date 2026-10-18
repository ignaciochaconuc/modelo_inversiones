# Phase 4C.2.2 — P0 integration in the synthetic runner

State: `nacho_evaluation_runner_p0_integrated_pending_authorization`.
Phase 4C.3: `not_started`. No real inference or comparison authorized/executed.

## Scope and compatibility

`tools/evaluation/nacho_evaluation_diagnostics.py` composes interpret_observed;
the existing runner routes to it only with a matching explicit profile and CLI
flag. Legacy calls still use interpret without sidecar persistence. No prompt,
acceptance predicate, attribution rule or reference changes. Existing v1 plans
remain readable; regenerating a plan necessarily reflects the new code hash.
See ADR-035. The optional metadata helper clock argument is for deterministic
fixtures; production uses the service's actual clock, never a historical run.

The new overlay `config/news_interpretation.evaluation.p0.yaml` points to the
unchanged evaluation runtime, with diagnostic version, enabled=true, policy,
90-day metadata retention and 24-hour response retention. Both opt-ins are
required. It does **not** renew the underlying price/capability attestation:
that profile expired 2026-10-15T20:39:20Z. Do not backdate a real preflight,
extend the dates without review or reuse the previous authorization.

## Offline checks

```powershell
python scripts/validate_news_diagnostic_sidecar.py --validate-only
python -m pytest tests/integration/test_nacho_runner_diagnostics.py
python scripts/run_phase4c2_attribution_evaluation.py --config config/news_interpretation.evaluation.p0.yaml --budget-usd 1.60 --diagnostic-sidecars --validate-only
```

The last command must currently block because the attestation expired. It still
verifies the pinned freeze/original cases before checking the runtime. No
credentials, transports, budgets, inference results or sidecars are loaded or
written by validate-only. Fixture preflights use new fabricated data, simulated
time and fictional settings, never expired historical response content.

## Future authorization procedure — not granted

After separately reviewing a current runtime profile, repeat the real offline
preflight above. Review its exact plan, full reservation, P0 code/policy and
all 32 source bindings. Create a new unique `eval-<32 lowercase hex>` identity.
The owner must approve a new authorization record with the existing fields
(approved, authorized_by, actual zoned authorized_at/expires_at, run_id,
max_provider_calls=32, budget_usd, freeze_sha256 and exact plan_fingerprint),
but version **nacho-evaluation-authorization-v2** and additionally:

`diagnostics_fingerprint = fingerprint(plan['evaluation_diagnostics'])`

Use the project's canonical fingerprint function, not a raw hash of pretty JSON.
The historical v1 authorization is invalid for P0 even if copied. The service
also enforces execution authorization, router, budget and one attempt; P0 adds
no tokens, retry, extra request or inference budget. Before each call check
authorization validity, freeze, overlay and underlying runtime hashes.

Future command, **do not execute without a separate approval**:

```powershell
python scripts/run_phase4c2_attribution_evaluation.py --config config/news_interpretation.evaluation.p0.yaml --budget-usd 1.60 --diagnostic-sidecars --confirm-real-inference --authorization <new-v2-authorization.json> --run-id <eval-new-UUIDhex>
```

## Artifacts, failure and audit

Existing attempts/ledger/case export remain in the new evaluation run directory.
Sidecars live separately in `data/cache/news_evaluation_diagnostics/<run_id>/`.
`diagnostic-bindings/<case_id>.json` pins each successful ID incrementally;
`diagnostic-manifest.json` closes the 32-case set and the output pins its SHA-256.
Both manifest/bindings contain closed metadata only, no source/model text.

Manifest entries bind case/source/request/revision/evidence/wire/cache identities;
the manifest binds settings, plan and diagnostic configuration. Accepted,
abstained and rejected native outcomes remain unchanged in output; sidecars use
their own grouped outcomes, including technical_error and explicit no-call
lifecycle not_run. A failed sidecar write preserves any completed delivery and
ledger, stops further provider calls and leaves diagnostics_complete=false
(CLI exit 2). Remaining cases have no-call sidecars where storage works. A
possible call without a record is never represented as a proven no-call.
Failures contain fixed codes only, not exception messages. No retry or backfill.

Pin the printed/exported manifest hash for later metadata-only audit:

```powershell
python scripts/audit_nacho_evaluation_diagnostics.py --manifest <new-run-directory>/diagnostic-manifest.json --expected-sha256 <pinned-manifest-sha256>
```

Audit reads only the manifest and sidecars, not response content or references;
it checks the complete 32-case map, pinned IDs and metadata fields. Missing,
altered, swapped, incomplete, future or expired metadata blocks the audit.
It does not certify semantic truth. Whole-store tampering is not prevented by
unsigned hashes; retain the pin independently. A failed final manifest write
requires manual review using incremental bindings, not automatic resumption.

## Retention and boundaries

Response TTL stays 24 hours. Sidecars expire exactly 90 days after creation;
the manifest expires 90 days from start and audit enforces both limits. No TTL
extension by rewriting metadata. Incremental bindings share the run metadata
policy. Access denial is not physical deletion: separately authorize an exact
list of expired manifest/binding/sidecar files before cleanup; preserve ledgers,
historical attempts, original responses and frozen references. No automatic
recursive purge. Do not generate metadata retrospectively for run01.

Tests exercise two new simulated 32-case runs with identical semantic output,
wire/reservations and accounted costs; stage/numeric/unknown-evidence/negation
subcodes; accepted/abstained/rejected outcomes; unknown-cost halt/no-call states;
sidecar-write failure with retained attempt; v1 authorization rejection and no
credential bootstrap; manifest tampering, incomplete audit and independent TTL.
No Finnhub, official TEST, real provider, ChatGPT comparison or Feature Store.

## Offline validation results

- Full final suite: `python -m pytest` — **770 passed**, 157.55 seconds.
- Dedicated integration suite: **17 passed**, synthetic temporary files only.
- `python scripts/validate_data.py`: feature/target separation valid; 905 news
  revisions, 811 logical articles, zero invalid hashes/missing lineage/duplicates;
  four valid enrichment snapshots.
- `python -m compileall -q src scripts tools/evaluation`: successful.
- P0 specimen preflight: validated_offline; zero provider calls, credential
  loads or persistence writes.
- Runner P0 preflight: deliberately blocked by
  `expired_or_future_evaluation_attestation`; no renewal or bypass performed.
- SHA-256 comparison: all **3,324 existing data/config/evaluation files**
  unchanged. The only existing src change is the backward-compatible optional
  metadata clock argument; validators, prompts, runtime schemas and algorithms
  remain byte-identical. The new overlay does not replace an existing profile.
- Frozen reference hash preserved:
  `1484dab560f898c71a857c40d3fe9ee3312981cbafdfa2eb4936b1e093fbfb39`.
- Historical run01 output hash preserved:
  `c9181bee95769a0d13928d768a3490c83de2377ba93aa9f60eb4252d14479fa4`.
- No real sidecar tree, new inference, authorization or retrospective diagnostic
  was created. Historical content was only hashed as bytes, never decoded or
  read through an expired response reader. Git status was unavailable because
  the installed git.exe is incompatible with this platform; conservation was
  checked against the per-file SHA-256 baseline instead.
