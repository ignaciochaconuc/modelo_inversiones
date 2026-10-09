# ADR-017: Causal walk-forward retraining robustness

## Status

Accepted.

## Context

Phase 3C found RF-Small 20d stronger than Ridge-100 on fixed validation. That
comparison does not show whether the advantage survives repeated causal
retraining or whether frequent retraining is worth its computational cost.
Using only `decision_date` as a cutoff would leak 20-session labels across each
model activation boundary.

## Decision

Phase 3D.1–3D.4 uses an expanding training window beginning 2010-01-04 and a
pseudo-out-of-sample walk-forward robustness period beginning in 2016. Before
every fit, training rows must satisfy both `decision_date < prediction_start`
and `target_end_date_20d < prediction_start`; equality is purged. Each fit gets
a new train-only preprocessor.

Schedules group contiguous XNYS sessions by month, quarter, half-year or year.
The fitted model and preprocessing statistics remain frozen within each
prediction period. Only the frozen RF-Small 20d profile and Ridge alpha=100 are
allowed. Both produce future-return predictions that are ranked
cross-sectionally; no direct-rank model is trained.

Operational frequency selection uses mean daily Rank IC with tolerance 0.003.
Among policies within tolerance of the raw best, the policy with fewer
retrainings wins; worst-year IC, ICIR, positive-IC share and top-10 uplift are
secondary tie-breaks. Timing is diagnostic and machine-dependent.

The official TEST beginning 2022-01-03 remains sealed. Prediction metrics may
use only labels whose `target_end_date_20d < 2022-01-03`; therefore the nominal
walk-forward range ends 2021-12-31 while the effective evaluable end is
persisted separately. The 2016–2018 portion is not described as an independent
holdout because it belonged to the original Phase 3B/3C TRAIN period.

Model-age metrics are computed inside each policy using XNYS sessions since
activation. Cross-frequency predictions are never pooled as independent
economic observations; the global interpretation uses each model's selected
policy and does not impose monotonic degradation.

## Consequences

Every result can be reconstructed from code, frozen configuration, fit-level
purge metadata and per-fit preprocessing metadata without serialized estimator
objects. This phase does not choose a final development model, vary the training
window, ablate feature families, open TEST, or create portfolio decisions.
