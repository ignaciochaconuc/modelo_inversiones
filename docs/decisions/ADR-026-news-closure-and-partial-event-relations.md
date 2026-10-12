# ADR-026: News technical closure and partial event relationships

## Status

Accepted by external review communicated by the project owner. Documentary
governance only; ADR-024/025 remain immutable history. 4B:
`completed_with_documented_limitations`; 4B.1:
`completed_ai_assisted_semantic_review`; 4B.2: `completed_targeted_improvement`;
4C: `not_started`. See [formal closure](../phase4b-closure.md).

## Context

Small ChatGPT-assisted reviews and a development duplicate correction support
technical acceptance, not exhaustive semantic certification. The separate
40-case review observed one missed shared event and no conclusive FPs;
real-positive coverage and independent human validation remain limited.
Multi-event roundups may partially relate to individual articles without
being duplicates or compatible single-event members.

## Decision

Keep v1 reproducible/default and v1.1 an opt-in conservative future-integration
candidate. No automatic production promotion. Preserve thresholds, factual
guards, complete-link, PIT, snapshots and raw evidence.

Clusters are versioned evidence, not exhaustive semantic truth or permanent
event IDs. Common ticker/company/topic/date is insufficient. Do not merge
roundups automatically with every mentioned story. Partial relationships need
not justify deduplication or common membership. Future 4C must admit individual
articles/singletons and cannot assume all relationships are discovered.

Keep AI-assisted provenance explicit; never combine development, synthetic and
external reviews into one clean holdout. Separate uncertain cases. Technical
closure is distinct from semantic-quality certification.

## Consequences

Recall, sparse positives, partial registry, observed-versus-retrospective
availability and Finnhub text/rights restrictions constrain future contracts
and claims, but do not block explicitly authorized 4C design. No design or
implementation is started. No algorithm, schema, runtime state or behavior
changes; final documentary states do not rewrite historical artifacts.
