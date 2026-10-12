# ADR-027: Individual news interpretation and derived-result PIT

## Status

Accepted for implementation of Phase 4C.1 only, `implemented_pending_external_review`.
No authorization for 4C.2/4C.3, external clients, inference campaigns or trading.
ADR-023–026 and the Phase 4B closure remain unchanged historical decisions.

## Decision and reason

Interpret an eligible **individual revision**, not a presumed single-event
cluster. A typed request contains original NewsRecord evidence, causal registry
entries and optional eligible context. Zero/one/multiple events are supported.
Evidence quotes are exact character-offset spans in captured headline/summary;
facts, explicit inferences and unknowns have distinct contracts. Unknown values
stay null; confidence is qualitative evidence sufficiency, never a calibrated
probability. Economic implications are not expected returns or trading advice.

Place contracts/replay under `agents.news_interpretation`, not in the data
layer: data must not depend on LLM infrastructure. Reuse NewsStore as-of,
existing temporal registry selection, hashing and LLMRequest/LLMResponse.
Do not implement a second router or change NewsAgent/AgentResponse. This is a
contract/replay boundary, not a new BaseAgent returning a different contract.

Evidence availability, actual generation, validation/derived availability and
experimental-use policy are separate. All 4C.1 responses are simulated or
experimental replay, **never operationally eligible**, even with strict inputs.
Derived availability cannot precede real generation/validation or any input.
Historical reconstruction cannot masquerade as contemporaneous interpretation.
Optional computed cluster context must itself be available by a strict cutoff;
strict registry entries must be known and valid then. Future registry additions
must not change a previous request fingerprint. Research requires explicit
proxy/retrospective opt-ins and keeps unverified markers and policy identities.

Use versioned schema, prompt, taxonomy and validation policies. Request,
evidence, prepared invocation, recorded response and resulting replay have
separate SHA-256 identities. Persisted-envelope JSON reconstruction is exact;
repeated new LLM inference is not promised deterministic, including temperature
zero. Cache identity includes revision, evidence, temporal policy/cutoff,
target, prompt/schema, model/provider and planned generation settings. Existing
AnalysisCache may use this full identity as source_id; no new cache is built.

Future calls must use BaseLLMClient/LLMRouter, CostTracker and PricingRegistry.
4C.1 only prepares LLMRequest and validates already supplied LLMResponse;
it does not select routes or call complete. Existing schemas can carry a JSON
output contract in prompt/content without extensions here. Future transport
support for generation parameters/structured-output capabilities must be
explicitly designed in 4C.2, not pretended to be enforced by prompt text.
Unpriced usage is unknown cost, not free. Budget rejection/retry/preflight and
operational cache/retention enforcement remain future implementation work.

Article text is untrusted, JSON-delimited data, never executable instruction.
No tools, retrieval or outside context are enabled. Structural/span/number/
state guards fail closed on invalid responses; they cannot prove semantic
entailment or guarantee LLM injection resistance. External evaluation must
measure those properties before quality claims. Replay preserves refusal,
insufficient evidence, neutral/not-assessed economics and technical failure as
distinct outcomes, without manufacturing neutral events on abstention.

## Evaluation and limitations

Freeze an external protocol before models: factual/entity/state/number fidelity,
contradictions, hallucinations, abstention, multiple events, injection, repeated
inference variability, usage/cost/latency. Separate objective quote/contract
checks from attributed qualitative review; separate development, calibration
and frozen evaluation. New fictional fixtures specify only verifiable facts;
semantic labels remain proposed and pending separate review, never model
ground truth. No Phase 3 TEST or old 4B development examples are reused.

No external clients, actual inference, persistent provider-content store,
Feature Store/model/portfolio/risk/execution integration or 4B changes. Licensed
content/response retention requires explicit rights verification in future work.
