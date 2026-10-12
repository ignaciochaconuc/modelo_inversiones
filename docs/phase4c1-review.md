# Phase 4C.1 — Interpretation contracts and evaluation design

Status: `implemented_pending_external_review`. Only contracts, validation and
offline simulations are implemented. 4C.2/4C.3 are `not_started`; no real
inference, NewsAgent replacement, provider calls or Feature Store integration.
Phase 4B remains formally closed with its documented limitations.

## Architecture and flow

ADR-027 introduces `agents.news_interpretation` so the data layer remains
independent of LLM infrastructure. Input construction reuses 4A as-of queries,
4B registry selection and fingerprints, without modifying either algorithm.
The interpreter interface reconstructs recorded experimental responses; it
does not extend BaseAgent or replace its required AgentResponse contract.

```text
Current eligible NewsRecord + optional eligible context/registry
  -> NewsInterpretationRequest (individual revision, evidence/policy identity)
  -> prepare_llm_request (existing LLMRequest; no routing or inference)
  -> supplied simulated LLMResponse
  -> replay_response: parse + structural/evidence validation + provenance
  -> NewsInterpretationResult + serializable ReplayEnvelope
```

`NewsInterpretationInterface` / `OfflineNewsInterpretation` provide exact
recorded-envelope reconstruction. No second router or live interpretation
service exists. Future inference must go through the existing BaseLLMClient /
LLMRouter. No new clients or dependencies, no schema extensions to existing LLM
or AgentResponse interfaces, and no alternate execution authority.

## Versioned contracts and taxonomy

- `NewsInterpretationRequest`: schema/prompt/taxonomy versions, original
  NewsRecord, decision time, strict/research policy, optional target, context
  revisions, eligible registry entries and optional 4B snapshot reference.
  Primary `news_id` / `revision_id` remain directly accessible; evidence IDs,
  request identity and evidence fingerprint are deterministic properties.
- `ExtractedNewsEvent`: source-grounded description, entities/roles, state,
  stage/negation, optional supported date, numerical claims and unknown fields.
  Event taxonomy v1: earnings, guidance, investment, financing, ma, regulation,
  litigation, product, partnership, management, macro, analyst_opinion, other.
  Unknown classes use explicit `other_type`, not fabricated classifications;
  taxonomy extensions require new versions/review.
- `EconomicInterpretation`: possible favorable/unfavorable claims, qualitative
  horizon/materiality, uncertainty/limitations and not-assessed/balanced/neutral/
  uncertain stance. No price targets, expected returns, weights or execution
  directives. Fact/inference/unknown are distinct categories; inference requires
  reasoning, source assertions require citations. Empty evidence does not force
  either economic polarity.
- `InterpretationPayload`: only model-supplied semantic JSON, isolated from
  provenance. Zero events on abstention; one/multiple on interpretation. No
  numeric confidence; qualitative evidence sufficiency is declared, uncalibrated.
- `NewsInterpretationResult`: request/revision/evidence/invocation/response
  fingerprints; schema/prompt/taxonomy/validation/model-configuration versions;
  actual generation/validation/input availability and strict/research opt-ins;
  outcome/reasons, optional
  usage/estimated cost and strictly whitelisted provider/model provenance.
- `ReplayEnvelope`: original request + result/recorded content, schema
  `news-interpretation-replay-v1`; reconstructs and checks the result against
  the request, response and policy. Altered references/outcomes are rejected.

Event keys are local extraction identifiers, not permanent economic event IDs.
Schemas are immutable, extra fields forbidden, UTC aware and non-finite values
rejected. Settings are typed, not arbitrary dicts that can contain API secrets.

## Evidence and multiple events

Exact half-open Unicode offsets point into captured headline or summary;
quotes cannot be fuzzy or invented. Source content never changes. Every event
quote comes from the primary article, not a context-only story. Every mapped
entity/security must have text evidence and an applicable registry entry;
provider tickers alone are analysis scope, not protagonist proof. Unresolved
names stay explicit instead of inventing corporate IDs.

Numbers preserve the printed decimal value, literal unit, scale and period.
Unknown unit/scale/period stays null; no silent currency/percentage conversion.
Supported event dates require an explicit ISO source date in v1; otherwise
date stays unknown (no date parsing guesses). Conservative guards reject
rumor/opinion/expectation promoted to confirmation, unsupported completion or
announcement, lost negation and conflicting same-event quantities.

These checks do not prove semantic entailment: quote cropping, irrelevant
facts, periods/metrics, implicit negation or unrecognized expressions still
require external review. Conservative lexical checks can also reduce recall.
Optional snapshot context never certifies a single shared event or substitutes
for primary evidence; separate clusters do not prove independent semantics.
Multi-event roundups may be decomposed; impossible decomposition abstains.

## Derived-result PIT

The store-backed builder selects latest eligible revisions first; missing,
future and obsolete revisions cannot be substituted. Future registry entries
are filtered, active intervals enforced; direct strict constructors reject
future registry values. Request metadata stores eligible entries rather than
the name of a future registry release, so future additions do not rename an
earlier input. Targets with an entity ID require eligible registry evidence.

Strict evidence must have availability and actual first-seen/ingestion no later
than decision time: no late retrieved text or publication proxy. This is an
interpretation-input restriction, not a change to Phase 4A's storage semantics.
Computed 4B context is allowed only when its cutoff, availability and strict
markers are eligible; a snapshot calculated today cannot add historical
knowledge to a past strict prompt. Omitting optional context remains valid.

Research can use publication/registry approximations only through explicit
opt-ins, retaining original availability and policy. Actual input availability
includes first-seen/ingestion, registry knowledge and computed context, not
only the retrospective proxy. Generation cannot predate actual inputs;
validation cannot predate generation. Derived availability equals their max.
Real clock is the default; supplied timestamps are for authentic recorded
replay/tests, never backdating a fresh validation.

Every 4C.1 result has `experimental_only_not_operational`: operational eligibility
is false even for strict inputs, at the original cutoff and later dates.
Retrospective reconstruction never becomes a historical trading input. Future
operational release requires separately authorized contracts/integration and
availability proofs; no backtest route exists here.

## Abstention, errors and prompt safety

Whole-article abstention reasons include generic headline, unidentified actor,
unverifiable opinion, unattributed rumor, inseparable events, contradictions and
insufficient evidence. It has no events/favorable/unfavorable claims and cannot
be labeled neutral/balanced economics. Neutral economics is a different declared
interpretation stance, not absence of evidence. Invalid JSON/evidence, simulated
transport failure/timeout and budget rejection are distinct execution outcomes.
Diagnostics use safe enumerated error codes, never echo malformed article/response.

Prompt v1 treats JSON-delimited articles as untrusted data. No retrieval, tools
or external context are enabled; injected instructions cannot execute Python
or route a provider. Structural tests verify isolation and reject investment
directives, but there are no model-level robustness results: delimiting data
does not guarantee an LLM ignores injection. Evaluation must measure that.

## Router, costs, cache and reproducibility

Existing LLMRequest.prompt and LLMResponse.content carry the structured contract
without altering their schemas. The prepared request uses agent NewsAgent/task
news_interpretation; it neither selects a route nor calls complete. The only
router invocation in tests uses an explicit in-memory simulated BaseLLMClient.
Planned model settings are versioned; provider/model mismatch is rejected.
The prompt does not claim to enforce temperature/seed or transport JSON modes.

Future 4C.2 must define route/model pinning, client capability/parameter transport,
preflight budgets, bounded retries/error accounting and exact request identity
using this router, not another. PricingRegistry/CostTracker remain unchanged;
priced usage must be recorded there in future work. Here cost is an explicitly
supplied estimate or unknown (never assume absent pricing means free).
Existing default-zero LLMResponse metrics are flagged not reported rather than
used as measurements. Budget-overrun behavior is tested on simulated estimates,
not implemented as live request orchestration.

Invocation fingerprint covers exact request/evidence, prompt/schema, cutoff/
mode/opt-ins, target, provider/model/revision/settings and budget. Use it as
AnalysisCache source_id with evidence/analysis version checks in future; no
second cache or live cache service is built. Stored response has its own hash;
result/envelope identity includes provenance and real times. Exact JSON replay
is reproducible; new inference even at temperature zero may differ. No promises
of provider/model equivalence or identical new output.

Only JSON serialization is implemented, not a provider-content persistence
pipeline. Future storage/cache must be licensed, retention-controlled, isolated
from Feature Store, and preserve original response bytes/provenance without
secrets or overwrite. LLMResponse.raw is excluded completely. No real article
texts or model responses are added to tracked files in 4C.1.

## Evaluation and verification

See [external protocol](phase4c1-evaluation.md), frozen before any actual model
execution. Objective evidence checks and qualitative semantic judgments are
separate; all references require honest provenance. Nine new fictional cases
carry literal source checks and split labels, not human semantic ground truth.
Separate unit checks review literal quotations without using model predictions.
Semantic adjudication/calibration/population validation remains pending.

Specific tests cover revision/registry future invariance, strict/research,
retrieval cutoff, optional computed context, zero/multiple events, rumor/opinion,
stages/negation, numbers/units/contradictions, quotations/dates/entities, economic
categories, malformed/duplicate JSON, abstention, budgets/errors, injection as
data, replay/tamper resistance, version/cache keys and unavailable telemetry.
Frozen Phase 3 and all original Phase 4A/4B evidence/code/config/ADRs are hashed
before/after. No official TEST, provider download or real inference is executed.

Executed final validations:

- Specific tests: **30 passed in 1.77s**.
- `python -m pytest`: **423 passed in 46.18s**.
- `python scripts/validate_data.py`: passed; 905 captures/revisions, 811 logical
  articles, zero bad hashes/missing lineage/duplicate records; four original
  enrichment snapshots validated.
- `python -m compileall -q src scripts`: passed.
- Separate local v1.1 integrity check: two snapshots validated.
- **3,071 original protected files** retain their exact pre-change hashes,
  including previous source/scripts/tests/config and ADR-023–026/4B closure.
  The only changed entry in the larger initial inventory is the authorized
  documentary ADR index. The 2,777-file frozen artifact subset fingerprint
  remains `42fde87be6765ddb2c1269360d8f16dc1a5d8ace2b9451208efa507a3b91c383`.

Reproduction:

```powershell
python -m pytest tests/unit/test_news_interpretation.py tests/integration/test_news_interpretation_pit.py
python -m pytest
python scripts/validate_data.py
python -m compileall -q src scripts
```

Created: `agents/news_interpretation/{__init__,schemas,inputs,replay}.py`,
two test files above, `tests/fixtures/news_interpretation_contracts_v1.json`,
ADR-027, this delivery and the external evaluation protocol. Updated only
README, ROADMAP, ARCHITECTURE, PROJECT_SPEC and ADR index among existing files.
No existing algorithms, schemas, router/client/cache/cost modules, AgentResponse,
NewsAgent, configurations or historical reports were changed. No real provider
calls, inference corpus, official holdout execution or trading occurred.

## Requirements before 4C.2

External review must approve schema/taxonomy, temporal eligibility, prompts,
abstention/security/evaluation protocol and known lexical limitations. Then
explicit project authorization is required, with model/route/parameter transport,
rights/retention, budgets/pricing/telemetry, retry/cache policy and separately
reviewed evaluation references frozen before trials. AgentResponse adaptation
and any calibrated-confidence meaning need review; do not invent confidence or
silently insert these records into features. 4C.2/4C.3 remain not started.
