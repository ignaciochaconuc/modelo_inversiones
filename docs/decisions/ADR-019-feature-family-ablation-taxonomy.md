# ADR-019: Feature-family ablation taxonomy and diagnostic policy

## Status

Accepted

## Context

The frozen RF-Small 20d candidate uses 52 `quantitative-baseline-v1` features.
Native and permutation importances from Phase 3C describe associations inside
fitted trees but do not show whether the model can retain its signal after an
entire related family is removed and retrained causally.

Phase 3D.6 therefore varies only the feature subset. Model parameters,
target, annual retraining, expanding history from 2010-01-04, strict dynamic
purge, preprocessing and the 2016–2021 pseudo-OOS period remain frozen. TEST
beginning 2022-01-03 remains sealed.

## Decision

Partition all 52 canonical features exactly once into ten auditable families:
returns, momentum, relative momentum, volatility, trend, liquidity/volume,
drawdown, market, relative risk and historical position. Evaluate only `full`
plus ten leave-one-family-out policies. Do not combine removals, use adaptive
feature selection, run permutation/SHAP analysis or mutate the official feature
set during this diagnostic phase.

Classify the arithmetic mean-IC delta against full using predeclared boundaries:
important at or below -0.005; moderately useful through -0.003; neutral strictly
between -0.003 and +0.003; small positive change from +0.003 to below +0.005;
and potentially harmful at or above +0.005. A family becomes a harmful candidate
only if the material mean improvement also passes worst-year, ICIR and top-10
stability floors.

The 66-fit real run reproduced the full Phase 3D.5 candidate exactly. Removing
volatility reduced mean Rank IC by 0.015822 and was the only strong contributor.
Removing liquidity/volume reduced it by 0.004668 and was moderately useful.
Historical position had the largest positive removal delta, +0.003518, but did
not reach the +0.005 material threshold. No family qualified as a harmful
candidate.

## Consequences

Keep all 52 official features unchanged for the later final-development-candidate
decision. Phase 3D.6.1 subset confirmation is not warranted by the predeclared
rule. Neutral classifications indicate possible joint redundancy under this
specific RF experiment; they do not establish causal irrelevance or authorize
column removal.

This decision does not open TEST, select a final model, run multi-family subsets,
start Phase 3E or connect forecasts to portfolio, risk or execution.
