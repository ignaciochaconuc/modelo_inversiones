# ADR-010: Corporate-action training contamination

## Status

Accepted

## Context

Split-only normalization is auditable, but spin-offs, stock distributions,
mergers, recapitalizations and share-class reorganizations can produce raw-price
discontinuities that a simple split factor does not explain. Inventing an
economic adjustment from price heuristics would hide uncertainty.

## Decision

Raw bars and normalized split/dividend records remain unchanged. A separate,
versioned event table under `data/processed/market/corporate_action_events`
stores detected and manually reviewed events, their evidence, `known_at`,
confidence and training-exclusion decision. Manual classifications live in
`config/corporate_action_overrides.yaml`; they never contain price adjustments.

Detection records an extreme split-adjusted return and corroborating evidence
such as an extraordinary distribution, residual discontinuity after a split, or
continuity in the provider-adjusted audit series. Extreme moves without that
evidence are `unexplained_price_discontinuity`, pending review rather than given
an invented corporate-action cause.

Feature flags use only events with `known_at <= decision_time`. The event window
is one session before through one session after, but no session is marked before
the information was available. Target flags may look forward across 5, 10 or 20
sessions because they are label metadata. Values remain stored for audit while
the corresponding training-eligibility flag becomes false. `target_rank_10d`
uses only uncontaminated labels and preserves its configured minimum asset count.

`training_eligible` exists only in an explicit supervised feature/target join,
combining `model_eligible`, feature cleanliness and label eligibility. Provider
symbol aliases apply only to requests; persistence retains internal tickers.

## Consequences

Potentially invalid training observations are excluded without deleting raw
data or label values. Inference does not depend on future labels or future event
knowledge. No total-return or complex-action adjustment engine is adopted in
Phase 1D.1.
