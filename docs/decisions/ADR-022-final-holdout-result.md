# ADR-022: One-time final holdout result

## Status

Accepted

## Context

ADR-020 froze `development-candidate-v1` and ADR-021 froze
`holdout-protocol-v1` before TEST access. On 2026-10-09 at
23:06:37.925550 UTC, explicit authorization opened the official 2022+ holdout
for its first and only statistical evaluation. The opening record was persisted
before Feature or Target Store rows were loaded.

The immutable identities were:

- candidate fingerprint
  `65bbec61f8fda0df24097267b777c882fec4410cecbeb89ff909622a1f8ef467`;
- protocol fingerprint
  `7b9c9fbef617ede2bc1e78cec3fb35ddfc5b2b13d049f189e088c03fa37032e6`;
- snapshot fingerprint
  `2fa2ccc185c11d734aaf8e2ffbe0ee149425651a804200022b7aac734b3b3b6f`.

## Observed result

The nominal range was 2022-01-03 through 2026-10-05. The last fully observable
20-session label was for decision date 2026-09-03. Twenty later decision dates,
2,020 rows, were excluded as an incomplete target tail. Five annual expanding
fits were executed for RF-Small and five for Ridge-100. Candidate, Ridge and
`momentum_20d` used the same 117,333 prediction keys across 1,172 decision
dates; no alternative model or portfolio backtest was run.

The candidate produced mean daily cross-sectional Rank IC
0.05657902409360866, median 0.05938193819381937, standard deviation
0.2622611045685684, ICIR 0.2157354754784693 and 58.959% positive dates. Top-10
uplift was 0.02357107254703597 and was positive on 61.604% of dates.

Annual mean Rank IC was:

- 2022: -0.046738500043283254;
- 2023: 0.13090433225338913;
- 2024: 0.04111386326862704;
- 2025: 0.08113335950819735;
- 2026 partial: 0.08681575896143681.

Four of five years were positive, but worst-year IC was
-0.046738500043283254. The frozen automatic result is therefore `marginal`:
mean IC, positive-year share and top-10 conditions passed, while the strict
worst-year condition `> -0.01` failed. No post-hoc discretion or rounding was
applied.

Ridge-100 mean IC was 0.01755166285414075. RF minus Ridge was
0.039027361239467914, classified `rf_outperforms_ridge`. The momentum diagnostic
mean IC was 0.004410924861788064; RF minus momentum was 0.0521680992318206.
These comparisons do not alter the absolute result.

Development mean IC was 0.06382512021589799. Holdout was lower by
0.007246096122289332 and retained a diagnostic ratio of 0.8864695264532471.
The frozen protocol imposed no pass/fail rule on this comparison.

## Decision and consequences

Close Phase 3 as `complete — frozen predictive candidate produced marginal
final holdout result`. Do not modify `development-candidate-v1` and do not
reoptimize against TEST. Any future investigation is a new development
generation; this opened sample is not a clean holdout for TEST-inspired
changes. Exact reruns are reproduction/resume only under the same candidate,
protocol, snapshot and range identities.

This result does not establish production readiness, portfolio profitability
or approval for trading. No News Agent, portfolio construction, risk,
execution, paper trading or later phase is authorized by this decision.

The final artifacts record `test_used=true`, `test_opened=true` and
`holdout_executed=true`.
