# ADR-025: Versioned targeted editorial equivalence

## Status

Accepted for implementation, pending external semantic review. Supplements
ADR-024 for explicit v1.1 only; v1 remains available and unchanged.
Phase 4B remains `implemented_pending_external_review`; Phase 4C not started.

## Evidence

The pre-change [diagnosis](../phase4b2-diagnosis.md) reproduces a real productive
false negative: candidates/entities/time were correct; headline core and both
cosine gates failed. Short summaries differed in wording/length, so headline
normalization alone cannot satisfy the original global gate. The AI-assisted
36-pair review is development, not independent human truth.

## Decision

Opt-in `news-groups-v1.1` and `unicode-word-bigram-v1.1` use the separate
`config/news_grouping_v1_1.yaml`. Defaults and original config stay v1. Reject
unsupported grouping/text combinations. Keep `news-enrichment-v1` and
`entity-resolver-v1`: no schema or resolver change.

Three phrase-local headline equivalences:

- `iPhone18` -> `iPhone 18`, preserving any intact numerical generation.
- `sluggish demand` -> `soft demand`; no general synonym/sentiment dictionary.
- Remove a terminal dash-delimited `Nikkei` credit only. Internal references,
  other publishers and substantive text after a credit are retained.

The new editorial route requires a normalization-induced change, exact
canonical substantive headline equality, common resolved corporate entity,
minimum eight substantive headline tokens, and original factual/time/text
guards. Roundups cannot use this route. Original cosine thresholds remain
0.90/0.65/0.55. Global cosine is reported unchanged but not a gate on this
additional exact-headline route. Headline cosine there is canonical, labeled
by the evidence reason. Normalization cannot turn variants into exact duplicates.

Product spacing also exposes hidden generation numbers to compatibility
guards. v1.1 conservatively abstains when full-text number sets, existing
action sets or explicit material state terms differ: increase/decrease,
approve/reject, announce/complete, rumor/confirmation, raised/lowered and
additional negation terms. Missing numbers on one side also cause abstention.
This is lexical compatibility, not semantic entailment; paraphrases may abstain.

Candidate blocks/ceiling, publication window, shared-event vocabulary,
complete-link, availability and revision selection remain unchanged. PIT/raw
contracts are untouched. New snapshots coexist in a separately ignored tree.

## Evaluation and consequences

Preserve old evidence/adjudication bytes; a new local role sidecar marks all
36 cases development with AI-assisted provenance. The old CLI prevents
renewed independent evaluation of that registered development review.

Reproduce v1 snapshot identities and compare identical 200/500 input and
registry fingerprints. Freeze new predictions before adjudication, exclude
every previously presented pair, and sample deterministic strata including
algorithm-proposed positives and adversarial cues. Proposals are not labels.
Sparse positive real coverage is reported; nine new fictional unlabeled cases
complement pending real review. No threshold tuning from evaluation is allowed.

One known development false negative is corrected, not evidence of generalized
recall/precision. Exact-headline reuse can hide factual distinctions outside
the guards. Shared-event recall remains limited. No LLM, embeddings, features,
provider calls, Phase 3 TEST or Phase 4C work.
