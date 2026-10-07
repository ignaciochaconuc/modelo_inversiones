# ADR-014: Supervised dataset and temporal validation

## Status

Accepted.

## Context

ADR-002 and ADR-009 separate future labels from inference features, while
ADR-010 excludes labels contaminated by complex corporate actions. Model
experiments additionally need a deterministic target selector and temporal
boundaries that prevent a training label from observing prices in the next
split. Calendar-day offsets and random row splitting cannot provide that
guarantee for exchange sessions or cross-sectional ranking.

## Decision

The supported horizons are 5, 10 and 20 XNYS sessions, with 10 as the default.
Each horizon materializes one primary price return plus classification and
cross-sectional rank labels derived from that same return. Average ties and a
minimum of 20 eligible assets remain the ranking convention. Each label horizon
also persists the exact `target_end_date_hd` used for `P(t+h)`. Target schema
version `corporate-action-safe-target-v3` supersedes v2.

`TargetSpec(task, horizon)` is the only model-layer selector and resolves the
target, horizon eligibility flag, end-date metadata and purge horizon. The
supervised builder joins physically separate Feature and Target Stores only on
`ticker + decision_date`, validates one-to-one cardinality, combines
`model_eligible`, point-in-time feature cleanliness and horizon eligibility,
and creates `X` solely from the canonical feature allowlist. Ranking additionally
requires a non-null rank label.

The official V1 fixed holdout uses complete `decision_date` cross-sections:

- train: 2010-01-04 through 2018-12-31;
- validation: 2019-01-02 through 2021-12-31;
- test: 2022-01-03 through the latest available target.

Train labels require `target_end_date < 2019-01-02`; validation labels require
`target_end_date < 2022-01-03`. Equality is purged. Test remains controlled by
horizon eligibility. An optional embargo, zero by default, removes the first N
XNYS sessions from validation and test. It is separate from purging and does not
change the label-overlap rule. The abstraction names the split type so a future
walk-forward implementation can reuse the contracts without being implemented
in Phase 3A.

Every build returns a versioned manifest with target and split specifications,
schema versions, universe, columns, date ranges, row/date counts before and
after eligibility and purging, generation time and best-effort Git provenance.
Future model output uses a strict out-of-sample prediction schema with model ID,
training cutoff, target identity and horizon. It contains no portfolio weight,
order, risk decision or execution instruction. Predictive metric contracts
distinguish pooled metrics from cross-sectional-by-date Rank IC summaries.

## Consequences

Experiments are reproducible and their label overlap can be audited directly
without recomputing exchange offsets. Adding a horizon requires extending the
central supported-horizon contract and target generation, not duplicating the
dataset pipeline. Positive embargoes reduce later-split samples by whole XNYS
sessions. Phase 3A provides no fitted model, model selection, portfolio mapping
or backtest forecast integration.
