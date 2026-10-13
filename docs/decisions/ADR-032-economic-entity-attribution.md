# ADR-032: Economic entity attribution distinct from corporate identity

## Status

Accepted for Phase 4C.2.2 implementation: `implemented_pending_external_review`.
Phase 4C.3 remains `not_started`. No external inference is authorized here.
ADR-027–031, both smoke records and their ledgers remain historical evidence.

## Context

The second smoke passed structural and quote validation, but its semantic audit
found corporate attribution unsupported by a platform mention. Exact text and a
valid corporate registry identity do not establish participation in an event.
This development finding is not an independent holdout or a reason to repair
the accepted historical response retrospectively.

## Decision

Add an explicitly opt-in model output `news-economic-selection-v3`, prompt v3,
internal economic interpretation/result/replay v3 and runtime/attempt v4.
The attribution policy is `news-economic-attribution-v1`. Preserve old readers,
settings, defaults, prompt constants, record identities and exact replay.

Each mention has an independent kind, corporate identity and attribution:
`direct_participant`, `supported_indirect`, `contextual_mention` or `unknown`.
The model cannot emit a ticker. An identity proposal needs a unique eligible
registry entry and an exact citation containing its corporate name/alias.
Products/platforms cannot resolve to their manufacturer. Missing or ambiguous
identities do not inherit parent tickers; ambiguous proposals are rejected.
Context may retain a resolved corporate identity without economic attribution.

Direct roles require an explicit named-party relationship quote anchored to the
same event's state evidence. Indirect relationships require both named parties
and an independently validated direct participant in that event. A deliberately
small English relation-frame policy fails closed on unsupported constructions;
word proximity, a product name or general thematic association is insufficient.
No aliases, registry data, grouping algorithms or date policy are expanded.

Reuse the unchanged exact-match resolver policy (unique occurrence, declared
field/revision, Unicode half-open offsets), then all original factual validators
through a validation-only legacy projection, plus attribution validation.
Keep original provider output, resolved evidence, validation result, versions
and fingerprints separate. No persisted response is migrated or reclassified.

Expose a revalidated typed consumer projection, not a flat list of mentioned
tickers. Context/unknown/indirect never produce a direct economic ticker.
Even reported direct participation is not confirmed economic exposure:
`confirmed_exposure = false` and `operational = false` are enforced literals.
Potential impact requires cited participation/relationship and a rationale; it
is a conditional assessment, not causal proof, an exposure estimate or returns.
No Feature Store or investment consumer is implemented.

## Consequences and limits

Conservative syntax, field-local overlap and unambiguous security identity
reduce recall. Unsupported language and complex corporate relationships must
remain contextual/unknown or lead to explicit abstention/rejection, not guesses.
Literal relation frames cannot establish semantic truth in all quotation,
negation or hypothetical contexts. Text alone may not prove economic causality.
Free-text rationales still need independent semantic review.

The typed projection blocks normal validated misuse; it cannot constrain code
that deliberately bypasses validation or reads nested identity tickers as
exposures. Such integrations are prohibited and require separate review.
Budget, authorization, PIT, cache accounting, retention and provenance remain
unchanged; cache identities include the new contract/prompt/validation policy.

New synthetic adversarial tests are development regressions, not population
metrics. Freeze policy and use fresh externally adjudicated event/entity/role
cases before technical closure or any future integration. See
`docs/phase4c2-2-economic-attribution-review.md`.
