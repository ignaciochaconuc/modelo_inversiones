# ADR-021: Frozen final holdout protocol

## Status

Accepted

## Context

Phase 3D.7 froze `development-candidate-v1` before any use of the official
holdout beginning 2022-01-03. A final evaluation becomes methodologically
irreversible when TEST is opened: changing the candidate, metrics, thresholds,
controls or temporal procedure afterward would turn the holdout into another
model-selection set.

Phase 3E.1 therefore defines the complete evaluation protocol before reading
any TEST feature or target row. It uses only the frozen candidate contract and
configuration metadata. No model is fitted, no prediction or metric is
computed, and Phase 3E.2 is not started.

## Decision

Freeze `holdout-protocol-v1` with status `frozen_pending_execution`. It
authorizes only candidate fingerprint
`65bbec61f8fda0df24097267b777c882fec4410cecbeb89ff909622a1f8ef467`
and has protocol fingerprint
`7b9c9fbef617ede2bc1e78cec3fb35ddfc5b2b13d049f189e088c03fa37032e6`.
The metadata-only snapshot fingerprint is
`2fa2ccc185c11d734aaf8e2ffbe0ee149425651a804200022b7aac734b3b3b6f`.

The future execution will use an annual XNYS causal walk-forward from
2022-01-03 through the nominal configured cutoff 2026-10-05. Each annual
activation creates a new preprocessor and fit over expanding history beginning
2010-01-04; both remain frozen within that period. Training rows must satisfy
`decision_date < prediction_start` and
`target_end_date_20d < prediction_start`, with equality purged. The effective
end is the latest decision date at or before the nominal cutoff whose 20-day
target is fully observable.

The primary metric is mean daily cross-sectional Rank IC. Secondary metrics
cover Rank IC distribution and ICIR, regression error/correlation, top-10
uplift, annual stability with partial-year flags, and diagnostic comparison to
the frozen development snapshot. Portfolio metrics are excluded.

The only controls are Ridge alpha 100 on `target_return_20d` with
`quantitative-baseline-v1` and `baseline-standard-v1` under the same temporal
policy, plus the existing unretuned `momentum_20d` ranking diagnostic. No other
model, horizon, feature subset, window, frequency, seed or ensemble is
authorized.

Absolute status is predeclared as follows:

- `hard_fail` when mean Rank IC is at most 0;
- `fail` when it is positive but below 0.01, or when top-10 uplift is at most 0
  while mean Rank IC is below 0.03;
- `pass` only when mean Rank IC is at least 0.03, worst-year IC is strictly
  greater than -0.01, positive-year share is at least 0.50 and top-10 uplift is
  positive;
- `marginal` otherwise.

Thus 0 maps to `hard_fail`; 0.01 is not a fail by IC alone; 0.03 can pass;
worst-year IC exactly -0.01 cannot pass; positive-year share exactly 0.50 meets
that condition; and top-10 uplift exactly 0 cannot pass. RF minus Ridge mean IC
above 0.003 means `rf_outperforms_ridge`, below -0.003 means
`ridge_outperforms_rf`, and both exact boundaries and the interval between them
mean `approximately_equal`. This relative conclusion never changes absolute
status.

The holdout is one-shot. Its first separately authorized execution must
permanently record the candidate, protocol and snapshot fingerprints, nominal
and effective range, evaluation identity and opening timestamp. Thereafter a
rerun is only a reproduction and requires those fingerprints and the complete
TEST range to match exactly; it is not a new statistical evaluation.

## Consequences

A pass permits Phase 3 to close as a successfully validated predictive
candidate, but does not establish production readiness, portfolio
profitability or trading approval. A marginal result is recorded without
modifying the candidate. A fail or hard fail is also recorded without
reoptimizing against TEST. Any TEST-inspired investigation belongs to a new
development generation, and the opened sample is no longer a clean holdout for
that change.

Any semantic change to candidate, range or snapshot identity, metrics,
thresholds, controls, walk-forward procedure, purge or one-shot policy requires
a new fingerprint and explicit decision; it cannot retain
`holdout-protocol-v1`. At acceptance of this ADR, `test_used=false`,
`test_opened=false` and `holdout_executed=false`; TEST remains sealed.
