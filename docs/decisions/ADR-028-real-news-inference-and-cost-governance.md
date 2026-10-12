# ADR-028: Routed real news inference, budgets and restricted persistence

## Status

Accepted for Phase 4C.2 implementation; `implemented_pending_external_review`.
The project owner technically accepts 4C.1 as `completed_with_documented_limitations`.
Its original protocol/contracts/evidence remain historical. 4C.3 is not authorized;
all interpretations remain experimental, never operational.

## Decision

Use existing BaseLLMClient/LLMRouter and opt-in OpenAI Responses REST over httpx.
Allow only the exact official HTTPS endpoint; no redirects/proxy inheritance.
Environment-only key, explicit model-specific capability attestation/settings,
no universal model, silent fallback, tools or retrieval. Strict transport JSON
Schema is followed by unchanged 4C.1 Pydantic/evidence/PIT validation.

LLMRequest gains an optional response_schema without disrupting other tasks.
A new attempt record wraps original ReplayEnvelope plus transport/telemetry.
Actual model/provider must match route/configuration. Generation, receipt,
validation and persistence are separate; cache hits preserve original generation.

PricingRegistry gains explicit public lookup; legacy missing-price estimate()
still returns zero. New flow requires sourced, time-valid, finite prices.
Before every attempt, durably reserve per-request/run budgets via SQLite
transactions: conservative UTF-8 wire bytes plus framing and capped output at
uncached rates. Known usage settles using configured prices; unknown telemetry
retains full reservation and unknown actual cost. Overruns halt further calls
and are reported. Estimates are not invoice accounting or tokenizer guarantees.
CostTracker gains nullable unknown metrics/cost and an unknown-count report.

Every attempt, including failures/refusals/invalid JSON, is recorded immutably.
Retry only configured transient errors within count AND budget; no permanent
auth/parameter/budget retry or automatic factual repair. AnalysisCache is an
index into hash-verified immutable records in an ignored restricted local tree.
Keys include revisions/evidence/context/policy/versions/model/effective settings.
Explicit content TTL rejects expired cache/replay. Physical purge requires
separate local authorization, never automatic deletion of previous evidence.

Single-article smoke CLI is disabled without explicit confirmation and critical
model/pricing/retention/budget configuration. It never downloads news. Only
simulated transports are used during implementation. No real smoke, comparison,
official TEST, 4B changes or Feature Store/model/risk/execution integration.

## Official references and limits

[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
supports strict schema with required properties/nullable unknowns, and separate
refusal/incomplete handling. [Responses REST](https://developers.openai.com/api/reference/resources/responses/methods/create)
is the transport. Unsupported local constraints can be omitted from the wire
projection but remain mandatory in Pydantic. Model compatibility is configured
from verified documentation, not automatically assumed. Structural validity
does not establish semantic accuracy or injection immunity.
