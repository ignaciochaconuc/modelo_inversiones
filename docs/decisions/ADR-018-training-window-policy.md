# ADR-018: Training-window policy for the development candidate

## Status

Accepted

## Context

Phase 3D.1–3D.4 selected annual retraining for frozen RF-Small 20d using a
causal expanding window. Phase 3D.5 asks whether discarding older observations
improves predictive ranking enough to justify an additional temporal
hyperparameter. The official TEST period beginning 2022-01-03 remains sealed.

The experiment varies only the training window over the 2016–2021 pseudo-OOS
period. RF-Small hyperparameters, `quantitative-baseline-v1`,
`tree-preprocessing-v1`, annual activation, strict dynamic label purge and all
metrics remain frozen. The policies are expanding from 2010-01-04, trailing
eight calendar years and trailing five calendar years, with both trailing
starts floored at 2010-01-04.

## Decision

Use the expanding window for the current development candidate. A trailing
window is considered equivalent when its mean daily Rank IC is within 0.003 of
raw-best; expanding is preferred inside that band because it uses all available
evidence, avoids another temporal hyperparameter and is operationally simpler.
A trailing result needs a mean IC improvement of at least 0.005, together with
non-deteriorating stability, before it is interpreted as concept-drift evidence.

The real run performed 18 fits. Mean Rank IC was 0.0638251202 for expanding,
0.0610375967 for trailing-8y and 0.0589459119 for trailing-5y. Expanding exactly
reproduced the prior annual RF artifact within the predeclared 1e-12 tolerance,
was raw-best and was selected. Neither trailing policy improved mean IC, worst
year IC, ICIR or top-10 uplift, so this experiment provides no evidence that
removing old history improves the frozen model.

## Consequences

Future development evaluation should retain all label-safe history beginning
2010-01-04 unless a later, explicitly authorized experiment revisits this
decision. Every fit must still satisfy `decision_date < prediction_start` and
`target_end_date_20d < prediction_start`; preprocessing remains fit only on the
current TRAIN slice.

This decision does not select a final model, open TEST, authorize feature-family
ablations, start Phase 3E or connect predictions to portfolio, risk or execution.
The Phase 3D.5 artifacts remain separate under
`data/reports/models/phase3d/window_sensitivity`.
