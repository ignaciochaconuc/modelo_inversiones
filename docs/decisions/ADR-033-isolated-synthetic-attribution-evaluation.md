# ADR-033: Isolated synthetic attribution evaluation runner

## Status

Accepted for the requested preparation only:
`nacho_evaluation_runner_prepared_pending_authorization`. No paid execution is
authorized by implementation. Phase 4C.3 remains `not_started`.

## Decision and reason

Prepare the existing NewsAgent-tagged interpretation service v3 (runtime v4),
not a new implementation of the public NewsAgent stub or AgentResponse. Reuse
LLMRouter, OpenAIClient, durable RunBudget, pricing, exact grounding, attribution
validation, CostTracker and restricted attempt storage without modifying them.
Keep instruments outside production in `tools/evaluation` and a dedicated CLI.

Only the original 32 fictional cases and neutral fictional identity table may
be adapted. The control plane checks the pinned freeze bytes, reconstructed
records and source manifests, but passes only original evidence and neutral
identity data to the adapter. No reference annotations, ChatGPT responses,
expected roles, hidden sampling strata or comparison scores enter the model
request. No real news retrieval, production registry or fallback is available.

The source has no factual news publication/observation/ingestion timestamps.
Its existing virtual decision clock provides the mandatory synthetic fixture
availability/observation/ingestion fields, explicitly under
`provided-virtual-fixture-clock-v1`. This is a fictional evaluation schedule,
not a claim of historical ingestion. Publication/event dates remain null.
Use strict input checks and actual current timestamps for generation, persistence
and derived availability. Synthetic tickers/security IDs are copied, not invented;
entity IDs are evaluation identifiers derived from corporate names, not inferred
real identities. No aliases are added. Preserve share-class ambiguity and filter
entries by original known/effective times, including exclusion of future Quillan.

Preflight builds every exact production wire and conservative reservation
offline, without dotenv, HTTP, budget DBs or inference-output persistence. It
checks full-run capacity, output caps, current price interval and short-context
band. A new evaluation-only sourced profile preserves the economic v3 prompt
and all historical profiles. One attempt per case, no retry or cache substitution.

Real execution requires both an explicit confirmation flag and an owner-declared
authorization record bound to a complete plan fingerprint, code/config/input
identities, freeze hash, unique run ID, 32-call ceiling, budget and actual timezone
timestamps after freeze. It loads repository dotenv only after these checks.
The runner rechecks authorization expiry and freeze/config bytes before each call;
the service checks price validity and durably reserves each attempt. A new output
directory claims the run ID atomically; existing runs cannot be overwritten or
automatically resumed. Authorization records are not digital signatures.

## Persistence, export and compatibility

Separate ignored evaluation runs store plan/authorization, immutable attempt v4
records, per-case outcomes and a 32-case comparator-shaped export. Native v3
values and evidence remain native, not adapted to the ChatGPT answers. Map
technical service outcomes to comparator categories while preserving native
outcome/error/diagnostics, unknown telemetry and all cost reservations. No
interpretation units are invented for rejected/abstained/unrun cases.

Unknown cost or reservation overrun stops subsequent calls; remaining cases are
explicitly not_run. Unexpected authorization/persistence failures halt, retain
the durable ledger and report possible attempt occurrence without manufacturing
a record ID or pretending a failed write is a replayable prediction. Such a run
needs manual accounting review; no automatic rerun. Validated success/abstention
and semantic rejection can continue when usage/cost are known.

Literal comparison is not semantic harmonization: references may use natural
language or different shapes. Owner review of alignments/disagreements is still
required. All entities retain confirmed_exposure=false and operational=false;
the export's identity ticker is not a claim of direct economic exposure.

## Limits

UTF-8 framing estimates, four-lane prices and durable reservations are application
controls, not invoice guarantees. Unknown cache writes are not zero and no cache
savings are assumed. Standard short-context profile only; other tiers, tools,
regional premiums or long context require separate verified configuration.
Current model alias is not an immutable snapshot. Source rights, human reference
independence, semantic entailment and causal impact are not certified.

Tests use simulated provider responses and temporary outputs only. No production
schema/prompt/algorithm, frozen reference, smoke, Phase 4B, Feature Store,
investment path or official Phase 3 TEST changes. See
[runner preparation](../phase4c2-nacho-evaluation-runner.md).
