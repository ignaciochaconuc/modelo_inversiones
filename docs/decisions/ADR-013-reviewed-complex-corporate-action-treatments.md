# ADR-013: Reviewed complex corporate-action treatments

## Status

Accepted.

## Context

ADR-011 blocks a historical run when a held position crosses a complex corporate
action whose economics are not represented by simple split/dividend handling.
That conservative default prevented artificial continuity, but the 2012 Kraft
spin-offs of Kraft and Abbott and the 2013 MetroPCS recapitalization have
sufficiently precise primary
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

### Record date vs regular-way entitlement

`record_date` records the issuer's legal record date. `entitlement_date` is the
session when this simulator observes ownership for the economic transformation;
the two dates need not be equal. The engine simulates only the normal parent
ticker and interprets every trade as regular-way. It does not simulate separate
ex-distribution or when-issued markets.

For a due-bill spin-off, regular-way parent shares trade with the distribution
right through the distribution date. A regular-way sale after record date also
sells the right, while a regular-way purchase acquires it. The treatment
therefore observes the parent position after the final regular-way close before
distribution. This is a simulation mapping of documented market mechanics, not
a redefinition of the legal record date.

The Kraft/Mondelez treatment records 2012-09-19 as the legal record date,
captures regular-way MDLZ quantity after the 2012-10-01 close, and creates one
KRFT share for every three
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

The Abbott treatment records 2012-12-12 as the legal record date, captures ABT
regular-way ownership after the 2012-12-31 close, and creates one ABBV share per
entitled ABT share before the 2013-01-02 open. ABT remains held. Tiingo's
34.649721 extraordinary dividend is consumed by the treatment. ABBV is both a
possible distributed holding and a configured development-universe asset: being
received does not mean a strategy selected it, but a later eligible allocation
may buy it normally. ABBV basis remains unallocated; Abbott's issuer reference
allocation is non-binding guidance and is not an active accounting rule.

### Security identity changes

Ticker strings are provider-facing identifiers, not permanent economic
identities. A reviewed treatment must confirm the provider's historical lineage
before connecting a parent and distributed security.

Google's 2014 distribution is the canonical identity-change case. Before the
event, `GOOG` was the exchange symbol for Class A. On 2014-04-03 Class A changed
to `GOOGL`, while the new Class C received `GOOG`. Nasdaq instructed data vendors
to carry Class A history into `GOOGL` and Class C when-issued history into
`GOOG`. Tiingo follows that restated representation: local `GOOGL` contains Class
A history from 2009; local `GOOG` begins on 2014-03-27 with Class C when-issued
history. There is no duplicated pre-event Class A history under local `GOOG`.
No provider alias or engine ticker branch is required.

From 2014-03-27 through 2014-04-02 Nasdaq's regular-way Class A market traded
with the Class C entitlement, while separate symbols represented Class A ex-
distribution and Class C when-issued markets. Because the simulator models only
regular-way ownership, Google entitlement is observed after the 2014-04-02 close
and processed before 2014-04-03 trading. The treatment leaves GOOGL unchanged
and adds one GOOG per entitled GOOGL. It consumes Tiingo's 567.971668 GOOGL
pseudo-dividend and no split. Both securities remain independent members of
`development_fixed`; receiving GOOG is not a strategy selection.

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
- Kraft Foods Group information statement: regular-way shares carried the
  distribution entitlement through the distribution date.
  <https://www.sec.gov/Archives/edgar/data/1545158/000119312512146220/d317589dex991.htm>
- Abbott 2013-01-01 Form 8-K: completed 1:1 ABBV distribution and legal record
  date.
  <https://www.sec.gov/Archives/edgar/data/1800/000110465913001016/a13-2169_18k.htm>
- AbbVie information statement: regular-way/due-bill trading, fractions, and
  first regular trading after distribution.
  <https://www.sec.gov/Archives/edgar/data/1551152/000104746913000017/a2212291zex-99_1.htm>
- Google registration statement and 2014 Form 10-K: 1:1 Class C dividend,
  record/payment dates, and separate Class A/Class C economics.
  <https://www.sec.gov/Archives/edgar/data/1288776/000119312514138800/d709408ds8.htm>
  <https://www.sec.gov/Archives/edgar/data/1288776/000128877615000008/goog2014123110-k.htm>
- Nasdaq corporate-action alert and FAQ: regular-way entitlement, ex-
  distribution/when-issued markets, ticker transition, and history lineage.
  <https://www.nasdaqtrader.com/TraderNews.aspx?id=ETA2014-24>
  <https://www.nasdaqtrader.com/content/GOOGLEfaq.pdf>
- T-Mobile US 2013-04-30 Form 8-K: 0.5 factor and exact USD 4.0491 cash amount.
  <https://www.sec.gov/Archives/edgar/data/1283699/000119312513193449/d527693d8k.htm>

## Consequences

- Reviewed events can preserve actual economic NAV without adjusted-price
  heuristics.
- Legal record dates, simulated regular-way entitlement observations, event
  detection, and processing dates remain distinct and auditable.
- Auxiliary holdings expand the engine's required market-data inputs, not the
  investable universe.
- Reports distinguish complete NAV performance from incomplete tax-basis P&L.
- Every new complex event still requires separate economic review, configuration,
  evidence, tests, and data before it can stop blocking a run.
