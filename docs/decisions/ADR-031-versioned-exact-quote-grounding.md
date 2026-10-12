# ADR-031: Versioned exact-quote grounding

## Status

Accepted for Phase 4C.2.1 implementation: `implemented_pending_external_review`.
No real inference/provider request authorized in implementation; 4C.3 not started.
ADR-027/028/029/030 and original smoke/ledger remain historical and unchanged.

## Reason

The first real smoke selected existing source text but supplied incorrect
character ranges. It remains `invalid_response`, development diagnostic evidence,
not independent evaluation. Source-dependent character arithmetic is separated
from model semantic selection; exact grounding and all v1 factual/PIT rules stay.

## Decision

Opt-in `news-quote-selection-v2` output / `news-interpretation-prompt-v2` ask for
`evidence_id` and exact `quote`, never model-generated offsets. A pure
`news-exact-quote-resolver-v1` searches ONLY the declared eligible primary-revision
field. No occurrence -> reject; more than one, including overlaps -> reject.
No fuzzy/Unicode/whitespace/case normalization, alternate field/revision lookup,
first-match choice or semantic repair. Unicode half-open offsets are computed
only for unique literal matches. Abstention remains an explicit model outcome;
an unresolved citation is invalid, not silently converted into abstention.

Model-selection DTOs copy frozen v1 structural fields with quote references.
They do not inherit semantic validators: after resolution ALL original internal
Pydantic/evidence/registry/state/date/number/economic/provenance validators run.
The original v1 `schemas.py`, `replay.py`, `inputs.py`, protocol and fixtures
remain byte-identical. Original provider content is never overwritten by the
derived validation representation or attributed to a new provider generation.

The grounded replay separately persists original response provenance, canonical
selection fingerprint, raw content SHA, resolved internal v1 payload, source/
quote fingerprints, per-field ranges, resolver version and completion timestamp.
Replay re-derives the transformation and compares resolution/result identities.
Grounded result uses `news-grounded-result-v2`, with original provider content,
actual generation and new prompt/validation versions. Its payload remains the
existing `news-interpretation-v1` domain contract. No false v1-prompt attribution.

New opt-in `news-inference-settings-v3` / `news-inference-attempt-v3` wrap this
flow while reusing transport/pricing v2. Legacy settings/attempts v1/v2 remain
readable without migration, additional fields or changed serialization/hashes.
Cache keys bind the new validation version, prompt/wire/settings/output/resolver;
no old cache hit can substitute for new interpretation. Completion is stamped
after grounding/validation; derived availability includes generation, input
availability and validation, and remains strictly non-operational.

Safe diagnostics contain enum stage/rule and sanitized schema-field paths only:
transport, telemetry, JSON, model schema, quote resolution, internal schema,
semantic validation or provenance. Never publish Pydantic inputs/error bodies,
source quotes, model responses, arbitrary JSON key names or secrets.

## Unchanged policies and limitations

Dates still require a literal ISO date in the quote, with paired date/evidence;
otherwise model must choose both null. No textual-date conversion or publication
date substitution. A future date parser needs another explicit version/decision.
Registry aliases remain corporate/security aliases, not product names. Product
mentions do not justify manufacturer tickers; names can stay unlinked. Prompt
explains these existing constraints; no registry or identity heuristic is added.

Exact quote matching is not semantic entailment. Unique but irrelevant quotes,
misunderstood roles and unsupported implications still require external review.
Repeated short names increase abstention/rejection; a longer exact unambiguous
quote is allowed, but no automatic expansion. V2 also restricts economic citations
to the primary revision (v1 could cite eligible context there), intentionally
narrowing scope. Synthetic tests and the observed smoke do not estimate quality.

Budget, one-attempt smoke, explicit authorization/.env gate, restricted storage,
TTL, failures/cost accounting and router remain enforced. No schema/prompt/price
default is silently migrated; new local profile is separate and time-limited.
See [technical review](../phase4c2-1-grounding-review.md).
