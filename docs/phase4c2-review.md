# Phase 4C.2 — Routed LLM integration, budgets and persistence

Status: `implemented_pending_external_review`. The project owner's authorization
accepts 4C.1 as `completed_with_documented_limitations`; its original delivery,
ADR-027, evaluation protocol, schemas, fixtures and evidence are preserved.
4C.3 remains `not_started`; no operational release, Feature Store, predictive
model, portfolio, risk or execution integration.

## Transport, configuration and router

The optional OpenAIClient now implements the Responses REST transport with
existing httpx; it remains disabled without explicit settings and enablement.
No dependency/SDK installation or universal model default. Allowed endpoint is
exactly `https://api.openai.com/v1/responses`, with redirects and inherited
proxies disabled. Key comes only from `OPENAI_API_KEY`; no dotenv/file loading,
header/error logging or key persistence. Ollama and other tasks remain unchanged.

[Official Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
guided the strict schema projection: required object properties, nullable
unknowns, forbidden extra keys and separate refusal/incomplete handling.
[Responses reference](https://developers.openai.com/api/reference/resources/responses/methods/create)
documents provider creation timestamps, usage details and capped output
including reasoning tokens. Unsupported local constraints are removed only
from the structural wire projection; original Pydantic/evidence validation
remains mandatory. No prompt-only claim of valid JSON.

Settings require model ID, endpoint, structured mode, output cap, timeout,
supported-parameter list, verified model-specific output/context limits and
sourced capability attestation. Temperature/reasoning effort must be supported
explicitly; seed is not silently sent to Responses. Capabilities must match the
selected model, output limit and estimated context fit before calls. This is
verification against an operator-approved profile, not automatic discovery or
proof of account access; the operator must verify the model's official page.

All calls pass existing LLMRouter. Exact route/provider/model and adapter settings
are checked before execution; returned model/provider must match, without silent
alias/fallback. Effective parameters and exact wire payload/hash are retained.
The news task requires a dedicated task/agent-task route: even a matching
default route cannot silently authorize it. Effective parameters mean explicitly
transmitted settings; unreported provider defaults remain unknown. Transport
requests synchronous execution (`background=false`); pending work cannot settle
an unknown final cost using incomplete usage. Failed permanent provider envelopes
do not retry merely because they returned HTTP 200.
Default OpenAIClient() still raises ExternalCallDisabled. LLMRequest gains only
an optional in-memory response_schema; serialization excludes it to preserve
old request/replay identities. The complete wire schema is separately hashed
and stored. BaseLLMClient/LLMRouter themselves are unchanged.

## Orchestration and temporal discipline

`NewsInterpretationService.interpret_revision()` uses the original 4C.1 builder:
latest eligible individual revision, causal registry and optional context,
strict/research with explicit opt-ins. `interpret()` revalidates the request,
prepares the original prompt plus strict wire schema, checks authorized cache,
verifies route/prices/budget, calls router, validates and records each attempt.
No web retrieval, provider news download, tools or model-selected external actions.

Original payload/replay schemas remain unchanged. A new versioned
StoredInterpretationAttempt wraps request, settings, wire, safe provider response,
cost record, timestamps, outcome and optional original ReplayEnvelope. The core
uses `retrospective_reconstruction` to validate recorded content from this later
execution; the wrapper separately identifies new inference versus cache versus
offline replay. It does not label a real call a simulation. Dataset provenance
distinguishes exploratory real responses from offline simulated development.

Provider `created_at` becomes core generated_at, not historical publication or
an invented timestamp. Client receipt, actual validation and persistence are
separate. Provider creation time is not necessarily response completion; derived
availability includes validation after receipt. Coarse/provider-skewed clocks
can fail provenance checks rather than silently backdate. All original
`experimental_only_not_operational` guarantees remain: no historical or future
operational use even with strict inputs. Later outputs never rewrite earlier IDs.

## Pricing, budgets and unknown telemetry

PriceSchedule requires explicit source, model, finite rates and UTC validity
interval. Input/output rates must be positive; a real free/promotional tariff
would need separate explicit policy approval. No current prices are hardcoded.
PricingRegistry.get_price() exposes unknown without changing legacy estimate()
(which still returns zero for unknown); this flow rejects unknown/stale/mismatched
prices before calls. Configured tariffs must cover the selected model's reported
normal/cache input and all output, including reasoning; unusual billing models
require a reviewed pricing extension, not an assumption of zero additional fees.

Conservative input bound is UTF-8 bytes of the entire wire JSON plus 256 framing
tokens; reserve capped output at configured uncached/highest input rates. This
is deliberately conservative, may reject otherwise affordable/context-valid
requests, and is not a universal tokenizer theorem or invoice guarantee.
Unexpected observed overrun is recorded and stops further attempts.

RunBudget durably reserves before each attempt in SQLite transactions, checking
both per-invocation/request and run caps. Pending reservations survive crashes;
existing run caps cannot be expanded on reopen. Known usage settles the bound
using the configured price table; missing/partial/invalid telemetry keeps the
full bound and unknown actual cost. HTTP failure is not assumed free. Every
retry needs a new reservation and contributes to total cost/accounted exposure.
Reported input/cache/output tokens and actual/requested model are separate.

CostTracker/LLMCallRecord accept unknown values retrocompatibly. Known subtotals
must accompany unknown_cost_count; no absent telemetry is fabricated as zero.
`usage_based_estimate` means reported usage times a sourced tariff, not a bill.
Original complete-record totals/aggregation tests retain their behavior.

## Error and retry policy

Maximum 1–4 attempts per interpret invocation, explicit delay <=10 seconds.
Timeout/disconnect/429/5xx may retry; incomplete/provider-envelope responses
and invalid local JSON/evidence retry only as configured/budgeted. Authentication,
authorization, parameter/route/model mismatch, refusal, secrets, price and budget
failures do not retry. Invalid/refused/incomplete outputs retain billable usage.
No repair prompt invents missing facts: retries are fresh controlled generations
from identical evidence, not automatic reconciliation.

Unexpected errors use safe codes; provider error text/headers are never printed.
Unknown outcomes retain reservations. Known key values in input are blocked
before calls/storage; returned echoes are rejected/redacted, with safe cost
telemetry retained. Explicit tool outputs are rejected. JSON/schema/evidence/
direction guards do not prove entailment or full semantic injection resistance.

## Immutable storage, cache and retention

Restricted root: `data/cache/news_interpretation` (already ignored by Git).
`attempts/<SHA256>.json` is content-addressed, immutable and checked on read;
every attempt has UUID identity so repeated generations never overwrite evidence.
`index` reuses AnalysisCache solely as a pointer; `budgets/<run-id>.sqlite`
contains identifiers/bounds/settlements, not article text or credentials.
No second cache/router. Bad/expired pointers cannot authorize retrieval.

Cache key includes news/revision/evidence/decision/context/strict-research opt-ins,
schema/prompt/validator, requested model/provider, effective parameters, complete
wire schema, capability and pricing policies. Records recompute their binding
and ensure durable response matches original interpretation provenance. New
settings/revisions/models cannot collide. Cache delivery costs zero **additional**
provider calls, preserving original costs/timestamps; historical original cost
is not relabeled free. Original generation remains available in the record.

Content TTL is explicitly 1–168 hours (example 24). Expired content cannot be
served from cache or reconstructed. This implementation does not silently delete
evidence: physical cleanup is a separate owner-authorized retention operation.
Before any real trial the operator must schedule restricted expired-file removal
under their source/provider rights, preserving only lawful non-content metadata;
expiry refusal alone does not erase disk bytes. Do not claim legal rights or
zero provider retention from `store=false`: verify source/OpenAI policies first.
Local access controls/backups are the operator's responsibility; Git ignore is
not encryption. Original Phase 4A/4B content is never touched by this store.

## Smoke instructions — prepared, NOT executed

1. Copy `config/news_interpretation.example.yaml` to a secret-free local config.
   Fill exact model/capability ID, verified context/output limits, supported
   settings, documentary source/time, explicit sourced rates/validity, positive
   request/run budgets and acknowledge restricted storage/retention. Nulls are
   intentional blocking placeholders. No model or price is selected for you.
2. Set OPENAI_API_KEY in the process environment; do not put it in YAML or logs.
3. Select one existing eligible revision and strict cutoff (timezone-aware UTC).
   No news is downloaded. Keep example max_attempts=1 for the first smoke.
4. Execute only after explicit authorization:

```powershell
python scripts/run_phase4c2_news_smoke.py --config config/news_interpretation.local.yaml --model "MODEL_ID" --budget-usd 0.05 --revision-id "REVISION_ID" --as-of "2026-10-12T13:17:53Z" --confirm-real-inference
```

Replace placeholders and use a budget no larger than your configured run cap;
0.05 USD is an illustrative explicit cap, not a price/affordability claim.
Without confirmation, missing key or critical settings, execution is blocked.
Only one article is allowed; retries may add paid attempts if explicitly enabled.
The report prints safe identities, validation status, tokens/cost quality and
conservative exposure, never article/model text or credentials. No real smoke
was run during implementation; CLI tests exercise help/disabled/blocked paths.

## Frozen evaluation and future comparison

`docs/phase4c1-evaluation.md` and its original fixtures are unchanged. Structural
tests do not validate semantic precision, calibrated confidence or investment
alpha. Development simulations, calibration, independent evaluation, real
exploratory responses and failures remain separate. No real labels or benchmarks
are fabricated. `plan_model_comparison()` prepares identities/settings/wire
fingerprints on one immutable request without storage, routing or inference;
no model comparison is executed and Phase 3 TEST is never used.

## Implementation files and validation

New: openai_settings; interpretation runtime_schemas/budget/persistence/service;
example configuration; opt-in smoke CLI; global offline test fixture; runtime
and smoke tests; ADR-028 and this delivery. Updated: OpenAIClient, optional
LLMRequest transport hint, PricingRegistry explicit lookup, nullable CostTracker
telemetry, relevant README/ROADMAP/ARCHITECTURE/PROJECT_SPEC and ADR index.
No dependencies, original 4C.1 interpretation contracts, NewsAgent, router,
4B algorithm/configuration, frozen Phase 3 or earlier evidence are changed.

```powershell
python -m pytest tests/integration/test_news_interpretation_runtime.py tests/integration/test_phase4c2_smoke_cli.py
python -m pytest
python scripts/validate_data.py
python -m compileall -q src scripts
```

All normal tests block real TCP/UDP connection and DNS, using BaseLLMClient
simulations/httpx.MockTransport. Closure validation results are recorded below.
Only public official documentation was consulted over the internet; there
were no LLM API/news-provider calls, additional news downloads or official TEST
execution. Phase 4C.3 and operational promotion remain unauthorized.

Executed final validation:

- New/runtime plus unchanged 4C.1 focused suites: **75 passed in 5.47s**.
- `python -m pytest`: **468 passed in 53.62s**, with real network/DNS blocked.
- `python scripts/validate_data.py`: passed; 905 captures/revisions, 811 logical
  articles; zero bad hashes, missing lineage or duplicate records; four original
  enrichment snapshots validated. Separate check validates two local v1.1 snapshots.
- `python -m compileall -q src scripts`: passed. Smoke `--help` works; valid real
  smoke was not invoked. The real `data/cache/news_interpretation` tree was not
  created; all runtime content/budget/cache tests use temporary directories.
- Before/after hashes preserve **3,077 previous files**. Only the four explicitly
  authorized LLM infrastructure files and documentary ADR index changed among
  the initial inventory. Phase 3 and 4A/4B evidence, 4C.1 interpretation schemas/
  replay, original evaluation protocol/fixtures, old ADRs and configuration remain
  unchanged. Frozen 2,777-file artifact fingerprint remains
  `42fde87be6765ddb2c1269360d8f16dc1a5d8ace2b9451208efa507a3b91c383`.

Remaining operational prerequisites: verified actual model/capabilities/pricing,
source/provider storage rights and local cleanup/access-control arrangements,
then an explicitly authorized first real smoke. Passing these offline structural
tests is not semantic-quality or real-account/model-access certification.
