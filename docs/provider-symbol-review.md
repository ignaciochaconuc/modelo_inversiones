# Provider symbol review

Review date: 2026-10-06. Provider: Tiingo EOD.

The internal universe identifiers are never changed by this review. Aliases in
`config/provider_symbols.yaml` apply only when constructing provider requests.

| Internal | Tiingo request | Provider metadata evidence | Decision |
|---|---|---|---|
| `BRK.B` | `BRK-B` | Berkshire Hathaway Inc - Class B, NYSE, start 1996-05-09; 4,466 bars returned for 2009-01-01 through 2026-10-05 | Alias accepted |
| `BK` | `BNY` | Tiingo `BK` resolves to Canadian Banc Corp - Class A on TSX with only five bars; provider search and `BNY` metadata resolve Bank Of New York Mellon Corp, NYSE, start 1973-05-03; 4,466 bars returned for the requested range | Alias accepted; wrong five-row provider identity replaced on authoritative refresh |

Evidence was obtained from the provider metadata, price and utilities/search
endpoints. The local diagnostic can be repeated with
`scripts/diagnose_provider_symbol.py`; credentials and authorization headers are
never written to its output.

