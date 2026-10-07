# ADR-013: Reviewed complex corporate-action treatments

## Status

Accepted.

## Context

ADR-011 blocks a historical run when a held position crosses a complex corporate
action whose economics are not represented by simple split/dividend handling.
That conservative default prevented artificial continuity, but the 2012 Kraft
spin-off and 2013 MetroPCS recapitalization have sufficiently precise primary
evidence to model the assets and cash actually received by shareholders.

A provider may encode a complex event as an extraordinary dividend, split, or
both. Applying those generic records in addition to a reviewed treatment would
double count value. A spin-off can also create a security that no strategy chose
and whose tax-basis allocation is not known.

## Decision

Complex corporate actions remain blocked by default. A run may cross one only
when its persisted `event_id` has a validated, versioned entry in
`config/reviewed_corporate_action_treatments.yaml`. Each entry fixes ticker,
event type, entitlement/effective/processing dates, timing, economic parameters,
provider action types consumed, evidence, notes, and treatment version. A
mismatch between the event and treatment fails explicitly; there is no heuristic
fallback.

Treatments transform portfolio holdings and cash. They never rewrite raw OHLCV,
adjusted history, strategy allocations, or eligibility. Provider split/dividend
records listed as consumed by a treatment are suppressed for that event session
to prevent double counting.

The Kraft/Mondelez treatment captures MDLZ quantity after the 2012-09-19 close,
uses the 2012-10-01 distribution date, and creates one KRFT share for every three
entitled parent shares before the 2012-10-02 open. MDLZ remains held. KRFT is a
corporate-action auxiliary security: the engine loads and values its raw data,
but it is not added to `development_fixed` or strategy eligibility. If the next
allocation omits it, the existing target-zero logic sells it at the following
raw open. Missing required KRFT data blocks the simulation.

No fiscal allocation between MDLZ and KRFT is inferred. KRFT therefore carries
`cost_basis_status=UNALLOCATED` and no `average_cost`. NAV/performance remains
complete, while trading P&L is marked incomplete and omitted from the aggregate
report. With fractional shares enabled, the exact entitlement is retained. With
fractions disabled, a non-integral KRFT entitlement blocks because the actual
net proceeds of the distribution agent's sale are not available; no proxy was
selected for this reviewed event.

The MetroPCS treatment captures the pre-event TMUS quantity after the 2013-04-30
close and, before the 2013-05-01 open, applies a 0.5 share factor plus USD 4.0491
per pre-split share. The cash is `RECAPITALIZATION_CASH`, not an ordinary
dividend, and does not enter trading P&L. The provider's 0.5 split and 8.10
post-split-equivalent dividend records are consumed by the treatment.

Every application emits a deterministic `CorporateActionTransformation` linked
to event ID and treatment version. Cash movements also retain the event ID.
The report contract is `backtest-metrics-v2`; it preserves the ADR-012 formulas
and adds recapitalization cash, treatment count, and cost-basis completeness.

Primary evidence:

- Kraft Foods Inc. 2012-08-14 Form 8-K and exhibit: record date, distribution
  date, 1:3 ratio, and fractional-share sale mechanics.
  <https://www.sec.gov/Archives/edgar/data/1103982/000119312512355657/d397214d8k.htm>
- Mondelez 2012-10-01 completion Form 8-K: completed distribution and resulting
  independent KRFT security.
  <https://www.sec.gov/Archives/edgar/data/1103982/000119312512411522/d418430d8k.htm>
- T-Mobile US 2013-04-30 Form 8-K: 0.5 factor and exact USD 4.0491 cash amount.
  <https://www.sec.gov/Archives/edgar/data/1283699/000119312513193449/d527693d8k.htm>

## Consequences

- Reviewed events can preserve actual economic NAV without adjusted-price
  heuristics.
- Entitlement dates are distinct from event detection and processing dates;
  purchases after entitlement do not receive distributions.
- Auxiliary holdings expand the engine's required market-data inputs, not the
  investable universe.
- Reports distinguish complete NAV performance from incomplete tax-basis P&L.
- Every new complex event still requires separate economic review, configuration,
  evidence, tests, and data before it can stop blocking a run.
