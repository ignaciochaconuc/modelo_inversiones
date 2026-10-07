# ADR-015: Sealed-test simple predictive baselines

## Status

Accepted.

## Context

Phase 3A created temporally purged train, validation and test partitions. Simple
model selection still risks leakage if preprocessing is fitted globally, if the
2022+ holdout is inspected, or if feature composition changes after observing
validation. Predictive comparisons also need cross-sectional metrics because
the eventual economic decision is made within each date, not only across pooled
rows.

## Decision

Phase 3B runs only in `selection` mode. Its runner contract contains TRAIN and
VALIDATION and has no TEST partition. Every global and experiment manifest
records `test_used=false`; validation predictions are restricted to
2019-01-02 through 2021-12-31. Final sealed-test evaluation is a later phase.

The fixed feature set is `quantitative-baseline-v1`, an explicit 52-column
allowlist. It excludes price levels, nominal ATR/MACD, sector placeholders,
agent features and all identifiers. Average dollar volume is replaced by its
`log1p` transform inside model preprocessing. `baseline-standard-v1` fits
median imputation and standard scaling on TRAIN only. An all-null TRAIN feature
fails; a zero-variance feature is excluded and recorded.

Phase 3B compares zero/train-mean regression baselines, a train-prior
classification baseline, causal momentum-20d ranking, ordinary least squares,
Ridge over the fixed alpha grid, and L2 logistic regression over the fixed C
grid. It does not implement specialized learning-to-rank. Hyperparameters are
selected exclusively on VALIDATION using the predeclared metrics, tolerances and
regularization tie-breaks. Regression and ranking emphasize daily
cross-sectional Spearman IC; classification emphasizes ROC-AUC. ICIR is mean
daily IC divided by sample standard deviation and is null when undefined.

Artifacts contain manifests, metrics, validation-only predictions,
preprocessing parameters and linear coefficients/intercepts. They are stored
under `data/reports/models/phase3b`; serialized estimator objects are not the
source of truth. Scikit-learn supplies standard algorithms and its version is
recorded.

## Consequences

Validation results can select a simple baseline without contaminating the final
holdout. Coefficients remain predictive associations, not causal importance.
Top-10 uplift is a cross-sectional diagnostic rather than a portfolio backtest:
it has no weights, cash, costs, Risk Manager or execution semantics. No horizon
is selected globally in Phase 3B.
