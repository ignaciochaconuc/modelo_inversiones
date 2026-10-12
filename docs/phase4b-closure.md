# Phase 4B — Formal technical closure

## Authority and final state

The external review communicated by the project owner authorizes technical
closure with documented limitations. This is governance acceptance, not
exhaustive semantic certification, population accuracy validation, deployment
approval or authorization to implement Phase 4C.

| Phase | Final governance status |
| --- | --- |
| 4B | `completed_with_documented_limitations` |
| 4B.1 | `completed_ai_assisted_semantic_review` |
| 4B.2 | `completed_targeted_improvement` |
| 4C | `not_started` |

These identifiers use the existing documentary `Status` convention; no runtime
phase-state enum is changed. They supersede documentary pending-review states,
not status fields in historical artifacts. Tool terminology such as
`human_adjudication_completed` does not certify human-independent provenance.
Original reports, labels, snapshots and ADR-024/ADR-025 remain unchanged.

## Approved scope, versions and configurations

Phase 4B closes deterministic exact/editorial deduplication, temporal entity
resolution, complete-link events, reproducible snapshots and capture lineage.
4B.1 closes the AI-assisted review; 4B.2 closes the targeted improvement and
separate follow-up review. Closure changes documentation only: no algorithms,
schemas, dependencies, tests, data, defaults or runtime behavior.

- Preserve `news-groups-v1` / `unicode-word-bigram-v1` and reproducibility.
- Adopt `news-groups-v1.1` / `unicode-word-bigram-v1.1` as the conservative
  **candidate for future integration**, not a production promotion.
- `config/news_grouping.yaml` and `NewsGroupingParameters()` remain v1.
- v1.1 remains opt-in via `config/news_grouping_v1_1.yaml`; future integration
  must explicitly select it. Resolver remains `entity-resolver-v1`, schema
  `news-enrichment-v1`, registry versioned and partial.
- Preserve thresholds 0.90 editorial, 0.65 headline, 0.55 event; 48-hour
  window, eight-token minimum, candidate ceiling, factual guards and complete-link.
  Preserve the v1.1 exact-canonical-headline route in ADR-025, where global
  cosine is reported but not a gate. No new exception or threshold adjustment.
- Do not rewrite raw evidence, snapshots or earlier results to reflect closure.

## Technical evidence

The [4B implementation](phase4b-review.md), [review protocol](phase4b-semantic-review.md),
[diagnosis](phase4b2-diagnosis.md) and [4B.2 delivery](phase4b2-review.md) retain
technical history. Metadata reports are `data/reports/news/phase4b_pilot.json`
and `phase4b2_comparison.json`; licensed evidence stays in ignored local trees.
Full snapshot/input/registry/parameter fingerprints remain in those reports.

The previous offline comparisons used identical input/registry evidence:
3,789 candidates on 200 articles, with zero groups in either version; 26,552
on 500 articles, with one editorial group in v1.1 versus zero in v1. No
shared-event pair was accepted. The sole new group is the Apple development
regression, not independent generalization evidence. Original v1 identities
and v1.1 outputs stay preserved, without regenerating these reports.

## Separate AI-assisted evaluation results

The project owner supplied and accepted the following adjudications. Both
were assisted by ChatGPT, separate from classifier predictions, but **neither
is independent human ground truth**. Do not pool them as one holdout or infer
population precision/recall from small enriched samples.

| Review | Cases | Different | Editorial duplicate | Shared event | Uncertain | Conclusive |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 4B.1 | 36 | 34 | 1 | 0 | 1 | 35 |
| 4B.2 | 40 | 37 | 0 | 1 | 2 | 38 |

4B.1 observed one duplicate false negative; Apple subsequently became
development. All original 36 cases are diagnostic/development material once
used to guide changes. Its v1.1 correction is a development regression only.

4B.2 observed one shared-event false negative and zero false positives in
conclusive cases. Zero **observed** FPs is not certified precision. The single
event positive and absence of conclusive real duplicate positives cannot
sufficiently validate recall. Uncertain cases remain separate, excluded from
conclusive results. No tuning is performed from these outcomes. The local
event FN ID is `2865a7bbb7930be623a9206833f9f31c7ba4d09ab8d36c75778fa4442aa4ff71`.

Review identities are preserved:
4B.1 `8b446f52bcfcaac6f40541e7e9298db5371f60e68e584775fc4e6b492afe4ca0`;
4B.2 `1f954cabead53b8a1af255ef53aa0f07eb12bd8a9f65c073077a21f835465cf2`.
The local 4B.2 aggregate records 40 adjudicated/zero pending/two uncertain,
while blind human-label fields remain empty. This closure documents the
supplied AI-assisted result, without inventing reviewers, dates or individual
labels. Historical pending summaries remain unchanged. Synthetic examples,
development regressions and external AI-assisted reviews stay separate; the
nine synthetic prompts acquire neither labels nor metric authority here.

## Architectural policy: events, roundups and partial relationships

[ADR-026](decisions/ADR-026-news-closure-and-partial-event-relations.md) records
the accepted interpretation without changing clustering:

- A cluster is versioned compatibility evidence, not exhaustive semantic
  certification or a permanent economic event identity.
- Common ticker, company, topic or date does not identify one concrete occurrence.
- Multi-event roundups must not automatically merge with every individual
  article they mention. Partial semantic relationships can exist without
  justifying deduplication or common membership.
- Distinct clusters/singletons do not prove semantic unrelatedness. Future
  4C must accept individual articles and cannot assume 4B finds all relationships.

These are consumer/governance constraints, not a claim that current lexical
guards recognize every roundup and not a new relationship-graph algorithm.

## Accepted limitations

1. Editorial-duplicate recall lacks sufficient external validation.
2. Shared-event recall lacks sufficient external validation; the observed
   event FN remains accepted and uncorrected by closure.
3. Independent real positives are scarce; AI-assisted labels are not human
   ground truth, and zero observed FPs does not establish population quality.
4. Entity registry coverage is partial, with ambiguous corporate/security
   resolution and incomplete historical identity coverage.
5. Historical publication is not historical local observation. Strict mode
   requires `available_at <= decision_time`; retrospective publication proxies
   and registry identities stay explicit research-only opt-ins/markers.
6. Finnhub headlines/summaries can omit context, updates and facts. Full text,
   entitlements and retention/redistribution rights are not assumed.
7. Synthetic, development and external AI-assisted evaluations must remain
   separate, with provenance and uncertainty exclusions.
8. Lexical factual/negation/state guards are not entailment. Candidate budgets,
   language coverage and partial relations limit recall; complete-link prevents
   transitive merging but does not certify semantic truth.

These limitations do not block **explicitly authorized future design** of 4C,
but condition its contracts and quality claims. Closure starts neither design
nor implementation.

## Existing contracts available to future Phase 4C

`NewsRecord` / `NewsStore.query_as_of()` supply eligible individual revisions,
with separate publication, first observation, availability and ingestion.
`NewsEntityLink` exposes entity/security attribution, evidence, ambiguity and
temporal status. `NewsPairEvidence`, `NewsDedupRecord`, `NewsEventCluster` expose
relationships, members and reasons; consumers need not discard ungrouped
articles or confuse editorial reuse with independent event coverage. Clusters
include singletons.

`NewsEnrichmentManifest` / `NewsClusterSnapshot` expose decision/computation
times, strict/research policy, versions, membership and fingerprints. Snapshot
membership IDs are not stable real-event IDs. `NewsEnrichmentStore.lineage()`
links members/identities to captures. Future consumers must explicitly select
a version, retain individual revision/source IDs, uncertainty and strict PIT;
never substitute computation time or retrospective publication for knowledge.
Existing `AgentResponse` / `LLMRouter` boundaries remain mandatory for future
agent work. No new 4C contract, LLM interpretation, sentiment, impact, features
or portfolio/risk/execution connection is implemented here.

## Closure validation and preservation

Before edits, 3,048 files were hashed: frozen Phase 3 reports/models/features/
targets, Phase 4A news, existing 4B snapshots/reports/reviews, source/scripts/
tests/configuration, ADR-024/025, pyproject and ignore rules. Compare every
recorded path after validation, including v1/v1.1 and evidence; preserve user
edits present at closure start. Generated bytecode/cache is excluded.

Required commands, without provider requests or official TEST execution:

```powershell
python -m pytest
python scripts/validate_data.py
python -m compileall -q src scripts
```

Executed closure validations:

- `python -m pytest`: **393 passed in 29.06s**.
- `python scripts/validate_data.py`: passed. 905 raw captures/payloads and
  normalized revisions, 811 logical articles; zero bad hashes, missing lineage
  or duplicate records. Four original enrichment snapshots validated.
- `python -m compileall -q src scripts`: passed.
- Additional read-only integrity check: two separate local v1.1 snapshots
  validated against the original News Store.
- All **3,048** protected before/after hashes match; zero changed/missing paths.
  Canonical file-map SHA-256 (the existing fingerprint convention):
  `87c8cce76a3821e126fff8ed2bfc210cd042911a73c967a47270d75eb22f63a0`.
  This includes source, scripts, tests, v1/v1.1 configurations, frozen Phase 3,
  Phase 4A/4B evidence, local adjudications and unmodified ADR-024/025.

Created: this closure and ADR-026. Updated: README, ROADMAP, PROJECT_SPEC,
ARCHITECTURE, `docs/phase4b-review.md`, `docs/phase4b-semantic-review.md`,
`docs/phase4b2-review.md`, `docs/news-groups.md` and the ADR index. All changes
are documentary. No pilot/evaluation report was regenerated. Artifact statuses
are deliberately not rewritten. No tuning, retraining, official holdout
execution/replay or external request occurred. Phase 4C remains `not_started`.
