# ADR-009: Feature and target storage separation

## Status

Accepted

## Context

Targets contain future information by definition. Storing them beside inference features makes accidental leakage possible even when column registries are disjoint.

## Decision

Persist production/inference features under `data/features/quantitative` and supervised labels under `data/targets/quantitative`. Both use the natural key `ticker + decision_date` and are joined explicitly only during supervised training. `FeatureBuilder` does not construct targets; target construction lives in `features.targets` and is invoked only through the optional `--with-targets` workflow.

Future corporate actions may be used to make target price returns split-consistent, but never for feature generation. Targets remain price returns and exclude dividends in Phase 1B.

Range rebuilds are authoritative for the requested tickers and dates: prior rows in that scope are removed before current results are written. This prevents stale features or labels surviving a historical correction.

## Consequences

Live/inference readers can load a directory that physically contains no labels. Training requires an explicit key join and validation. Two datasets and their lifecycle must be managed, but leakage risk is materially reduced.
