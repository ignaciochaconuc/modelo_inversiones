# ADR-016: Sealed-test nonlinear model selection

## Status

Accepted.

## Context

Phase 3B established linear/logistic baselines without opening the 2022+
holdout. Testing whether nonlinear trees add signal requires holding the data,
features, targets, split, metrics and leakage controls fixed. An adaptive search
after observing validation would make that comparison difficult to interpret.

## Decision

Phase 3C remains in `selection` mode and its runner receives only TRAIN and
VALIDATION. Every artifact records `test_used=false`; TEST predictions, metrics
and feature importance are prohibited.

The feature set remains the exact 52-column `quantitative-baseline-v1` allowlist.
`tree-preprocessing-v1` applies the two established liquidity `log1p`
transformations, fits median imputation on TRAIN, performs no scaling, fails on
all-null TRAIN features, and explicitly records/excludes zero-variance features.

Random Forest, XGBoost and LightGBM each use three frozen profiles with
`random_state=42` and `n_jobs=-1`. There is no adaptive tuning or early stopping.
Each profile is fitted for three regression targets, three classification
targets and three direct-rank targets: 81 fits. Twenty-seven additional ranking
evaluations reuse regression predictions and do not fit another estimator.

Selection first chooses a profile/approach inside each family and task/horizon,
then compares the three family winners. Regression/ranking use mean daily
cross-sectional Spearman IC with tolerance 0.001, followed by ICIR, positive-IC
frequency, worst-year IC and lower complexity. Classification uses ROC-AUC with
tolerance 0.001, followed by Log Loss, Balanced Accuracy, worst-year AUC and
lower complexity. Only VALIDATION 2019–2021 participates.

Native and permutation importance are persisted only for the 27
family/task/horizon winners and are diagnostic. They cannot change the feature
set, trigger retraining or affect selection during Phase 3C. Top-10 uplift is
also a predictive diagnostic, not a portfolio backtest.

## Consequences

Phase 3C can attribute differences from Phase 3B primarily to model family and
complexity while retaining an untouched final holdout. Its real-data run stores
81 fits, 108 evaluations and 27 importance artifacts under
`data/reports/models/phase3c`. No selected model is a final trading model, and a
later explicitly authorized phase is required before TEST evaluation.
