# ADR-012: Backtest performance metrics and benchmark methodology

## Status

Accepted.

## Context

Performance can be distorted if it is measured from fills instead of portfolio
value, if costs are deducted twice, or if a price-only benchmark is compared
against a portfolio that receives dividends. Metric formulas and annualization
must remain reproducible across reports.

## Decision

The methodology version is `backtest-metrics-v1`. Final session NAV snapshots
are the sole source of portfolio returns:

`r_t = NAV_t / NAV_(t-1) - 1`.

Cumulative return is `NAV_final / NAV_initial - 1`. CAGR uses actual calendar
days: `(NAV_final / NAV_initial) ** (365.25 / calendar_days) - 1`; it is `None`
when there are not two distinct dates. Volatility is sample standard deviation
with `ddof=1`, annualized by `sqrt(252)`.

Sharpe uses arithmetic daily mean, sample daily standard deviation, 252 periods,
and risk-free rate zero. Sortino uses minimum acceptable return zero and downside
series `min(r_t, 0)`; downside deviation is its root-mean-square annualized by
`sqrt(252)`. Both ratios are `None` when observations or denominators are
insufficient. NaN and infinity are rejected rather than silently discarded.

Drawdown is `NAV_t / running_max_NAV_t - 1` and maximum drawdown is non-positive.
The report records peak, trough, and the first recovery to peak NAV when present.

Transaction metrics use one execution record per attempted order. Filled,
partial, and unfilled rates use execution records as denominator; orders queued
beyond the report end are separately pending. Costs equal commissions plus
reported slippage cost. Slippage is not deducted again because fill price already
contains it economically.

Daily turnover is gross executed fill notional divided by final NAV of that
session. Total turnover sums daily values; average includes sessions without
fills, and annualized turnover is average daily turnover times 252. Unfilled
orders never contribute.

The reporting benchmark is an internal SPY total-return simulation, not a Phase
2B strategy. It begins with the portfolio initial capital, decides after the
first session close, and buys at the next raw open. It uses the same commission,
slippage, fractional-share policy, range, calendar, split handling, and dividend
entitlement semantics as the portfolio. Dividend cash credited post-close is
reinvested at the next raw open. Adjusted prices are never used. Missing entry or
temporally invalid data fails explicitly.

## Consequences

- NAV return remains distinct from realized plus unrealized trading P&L.
- Dividends and cash-in-lieu are reported separately from trading profit.
- Portfolio and benchmark are comparable after identical market frictions.
- Short samples can legitimately produce `None` for annualized ratios.
- Reports are deterministic, JSON-serializable, and carry methodology version,
  run ID, configuration, and survivorship-bias warnings.
