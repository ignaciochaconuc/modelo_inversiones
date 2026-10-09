# ADR-020: Frozen final development candidate

## Status

Accepted

## Context

Phases 3B–3D.6 accumulated fixed-validation and causal walk-forward evidence
without opening the holdout beginning 2022-01-03. A single machine-readable
specification is required before any future TEST evaluation so that no model,
feature or training-policy choice can adapt after seeing holdout results.

Phase 3D.7 performs no new model search and does not train a final estimator.
It reads only persisted development summaries, verifies identity and metric
reproduction across phases, and freezes the procedure that may later be
evaluated under a separately authorized holdout protocol.

## Decision

Freeze `development-candidate-v1` with status
`selected_for_final_holdout_evaluation`:

- regression on `target_return_20d`, used as cross-sectional percentile rank;
- RF-Small with 300 trees, depth 4, minimum leaf 100, square-root feature
  sampling, bootstrap, random state 42 and `n_jobs=-1`;
- all 52 ordered `quantitative-baseline-v1` features;
- `tree-preprocessing-v1`, including train-only median imputation and `log1p`
  for ADV 20d/60d;
- annual retraining with an expanding history beginning 2010-01-04;
- strict purge requiring both decision date and 20d target end before the next
  prediction start, with equality removed.

The candidate fingerprint is
`65bbec61f8fda0df24097267b777c882fec4410cecbeb89ff909622a1f8ef467`.
The ordered-feature hash is
`55f32fa21661f33134746a577aef3e7da7816d8a33d02f52f8b1ee2d0a87501c`.
The canonical fingerprint covers every frozen predictive dimension and excludes
timestamps, timings and Git state.

Twenty days had the strongest Phase 3C mean IC, ICIR and worst-year result and
the largest improvement over Phase 3B. RF-Small materially exceeded Ridge in
annual walk-forward analysis. Annual was raw-best while requiring only six
fits. Expanding was better than both trailing windows. Ablations found
volatility strongly contributive, no harmful candidate and no reason for a
confirmation subset, so all 52 features remain.

## Consequences

The candidate is ready for a future final-holdout evaluation protocol, but it
is not production-ready, approved for trading or a final trading model. TEST is
still sealed; no final 2010–2021 estimator has been fitted and no portfolio
backtest was run in Phase 3D.7.

Any change to model/profile, hyperparameters, ordered features, preprocessing,
target/horizon, retraining frequency, training window or purge rule must create
a different fingerprint. It cannot continue under `development-candidate-v1`
without a new explicit decision before TEST evaluation.
