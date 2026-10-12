# Phase 4C.1 — External interpretation evaluation protocol v1

Status: design frozen before any real model execution; external semantic review
pending. No model benchmarks or population quality metrics are reported here.
Phase 3 official TEST and the inspected 4B cases are excluded from all splits.

## Datasets and separation

Development tests validate contract/temporal behavior using new fictional
articles and simulated JSON. `tests/fixtures/news_interpretation_contracts_v1.json`
has separately declared development, calibration and evaluation scenario IDs.
Its literal quotations can be checked mechanically against text. It contains
**no model-generated or supposedly human semantic labels**. Literal-check
fixtures are not a semantic holdout: tests inspect them and implementing agents
authored them. Their reference status is explicitly semantic-review-pending.
Before model comparisons, freeze a larger separately reviewed evaluation set;
never claim these nine prompts establish coverage, calibration or accuracy.

Future synthetic reference answers may include only unambiguous source-backed
facts, and require separate attributed review before they become reference
truth. Event/economic interpretations remain proposed until adjudicated.
Record reviewer identity, actual timezone-aware time, rationale, source spans,
uncertainty, review assistance and agreement/disagreement. Do not infer labels
from predictions, give implementing LLM output reference authority, or silently
upgrade AI-assisted review to independent human ground truth.

For future real review, verify licensing/retention first, freeze the revision
universe and strict cutoff, select deterministic/enriched strata, and preserve
exact evidence identities. Keep article-only evidence blind to provider/model,
proposed outputs and strata during initial reference annotation. A separate
anonymized-output assessment may then score extraction/economics; retain model
metadata separately for later cost/latency analysis. Do not overwrite evidence
or reference edits on rerun. No real review bundle is prepared in 4C.1.

## Predeclared measurements

| Dimension | Objective checks/denominator | External qualitative judgment |
| --- | --- | --- |
| Facts and hallucinations | Exact valid spans, unsupported/corrupted claims per substantive claim | Whether cited text entails the assertion; invented causal/relationship claims |
| Entities and roles | Name spans, eligible registry mapping, unresolved/ambiguous counts | Protagonist versus mentioned/provider-tagged entity; corporate/security distinction |
| State and stage | Rumor/opinion/expectation labels, negation/stage consistency, confusion matrix against reviewed labels | Confirmation versus report/expectation; announcement versus completion |
| Numbers and units | Exact value lexemes/Decimal, units/scales/periods, discrepancy rate per numeric claim | Context matching, comparator/period/entity relevance |
| Contradictions | Same-event contradictory numeric rejection; contradiction/abstention flags | Recognition of conflicting evidence and relevant updates across events |
| Abstention | Rates by reason, technical failure counted separately; reviewed sufficient/insufficient confusion | Appropriate refusal versus unnecessary loss of informative evidence |
| Multiple events | Reviewed event precision/recall, missing/extra events and correct source revision | Meaningful decomposition, roundup/partial relationship handling |
| Economics | Fact/inference/unknown categories, evidence/rationale completeness, prohibited-output violations | Plausibility, balance, conditionality, materiality/horizon/limitations; never return accuracy |
| Injection | Invalid instructions echoed as decisions, schema violations, attempted retrieval/tool actions | Does output follow article instructions or lose source facts? |
| Repeatability | Exact replay hash equality; new inference agreement/edit-distance/event-number differences across runs | Material factual variability between runs/models/providers |
| Cost and latency | Reported tokens/cache/output/cost per attempt/article; median/p95 latency; unknowns excluded and counted | Operational suitability under a separately authorized budget |

Do not use absent telemetry defaults as measurements. `tokens_reported` and
`latency_reported` distinguish existing LLMResponse default zeros from supplied
usage. Missing pricing is unknown, not zero. Distinguish first inference,
retries, cache replay and validation overhead. Report rejected/failed attempts
and costs rather than dropping them from economic denominators.

## Adjudication and analysis

Before execution, freeze corpus/references (or blind pending annotation),
schema/prompt/validation policy, model/provider/revision/settings, seeds,
per-case budgets, repeats and retry policy. No recommendations of current
providers/prices/models are made in 4C.1. Future policies require authorization
and explicit configuration, not changes chosen from frozen-evaluation results.

Keep development for fixes, calibration for any eventual confidence mapping
and frozen evaluation for conclusions. Current `evidence_sufficiency` is a
declared qualitative assessment only, not calibrated confidence. No numeric
confidence or empirical calibration is provided. If evaluation cases guide
changes, retire them to development and obtain new evaluation before claims.

Require independently reviewed conclusive references to compute extraction
precision/recall. Report unknown/ambiguous cases and adjudicator disagreement
separately; exclude inconclusive references from conclusive denominators.
Report all sample sizes and sampling enrichment. Do not pool synthetic,
development, calibration, real AI-assisted and independent human evaluations.
Small/enriched samples cannot estimate population quality or investment alpha.

## Acceptance gates for future experiments

Before authorized experiments: all contract/PIT regressions pass; zero accepted
fabricated quote/revision/provenance or temporal-policy violations in structural
tests; no operational release of simulations; review/licensing and budget/
telemetry procedures approved. Any observed hallucination, injection success,
unverified quantity or state promotion must be logged and attributed, not hidden
as neutral interpretation. These are procedural/structural gates, not a claim
of zero semantic errors. Semantic acceptance thresholds and statistical power
require separate pre-execution external approval, not post-hoc optimization.

All provider calls, repeated real inferences, cost benchmarks and automated
evaluation infrastructure remain unimplemented. 4C.1 evaluates contracts only.
