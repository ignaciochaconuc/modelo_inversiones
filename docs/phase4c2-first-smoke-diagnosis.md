# Phase 4C.2 — first real smoke: offline diagnosis

Analysis date: 2026-10-12. No new inference, provider request, dotenv bootstrap,
prompt/algorithm/contract change or 4C.3 work. The real response remains rejected;
this analysis does not certify its economic interpretation or promote it into
external evaluation. New regressions use independently authored synthetic text.

## Integrity, provenance and retention

Record: `3e354b82a8bf6aab2808dca0e770c7db74b29c4d947fcea7df2e0820b29c362d`,
in `data/cache/news_interpretation/attempts/<record_id>.json`.

- Original file SHA-256:
  `fb73e309073f6efd1ffc14cfe71de5f2b34ab771380906e98ab0b9bb7ab2fd24`.
- Canonical record fingerprint equals filename/record ID. File-byte SHA and
  canonical JSON fingerprint intentionally identify different representations.
- `news-inference-attempt-v2` validates, including inner ReplayEnvelope equality,
  request/evidence/configuration/cache/wire/response bindings and cost provenance.
- Wire fingerprint:
  `fbbc5e00de6c20277e9166148cdc7b3461ab904e38048cabcac015f3c129f61b`.
- Recorded response fingerprint:
  `9909dd8ce6d90e277deaeb5d671fb52b10e24b2d327105553b1e4f71a0839b23`.
- Provider content SHA-256:
  `0b960e07e2a5ce63e0f9aac02a184341aee1ddd053f9589e055831918cbb4d2c`.
- Requested and actual model both `gpt-5.6-luna`; dataset role
  `exploratory_real_response`, not synthetic/external holdout evidence.
- Inputs available/cutoff `2026-10-12T13:17:53Z`; generation
  `2026-10-12T22:00:22Z`; validation/derived availability
  `2026-10-12T22:00:28.290302Z`; persistence
  `2026-10-12T22:00:28.303534Z`. No historical LLM availability is asserted.
- Expiration **`2026-10-13T22:00:28.303534Z`**, valid at diagnosis. No backdated
  replay or retention extension. Source/revision/eligible registry reconstructed
  locally and match the stored request and evidence fingerprints exactly.
- Exactly one ledger reservation, read using SQLite read-only/immutable mode:
  attempt/cache identity, budget caps, reservation and settlement all match.

Input 4,729 = **3 ordinary + 0 cached reads + 4,726 cache writes**; output 878.
Cost `(3*0.20 + 4726*0.25 + 878*1.20)/1e6 = USD 0.0022357`, consistent with
the ledger and below USD 0.00722385 reserved / USD 0.05 budget. Cache-write
accounting is not the cause of rejection. Floating representation ending in
`...9999998` is not an additional billing charge.

## Rejection stage

1. Stored Responses wire uses strict JSON Schema; exact transport preparation
   is reproduced locally. The payload satisfies the **stored projected wire
   schema**, checked offline with Draft202012Validator (zero errors). Original
   HTTP headers/status/raw envelope are not retained, so they cannot be audited
   independently. Durable outcome is consistent with the successful adapter
   path, not timeout/refusal/truncation; no transport defect explains the failure.
2. JSON parsing with duplicate-key detection passes.
3. Pydantic fails at `EvidenceSpan.offsets`: **seven primary length mismatches**.
   An eighth error, `events[0].evidence: too_short`, is cascading after its two
   invalid children; it is not a separately missing evidence list.
4. The production cross-evidence validator was **not reached**. Independent
   read-only inspection finds all eight supplied quote slices incorrect. Every
   quote occurs verbatim somewhere in its declared field, but the supplied
   offsets select the wrong substring; evidence IDs are known/primary.

No headlines, source excerpts or full model output are reproduced below.
Ranges are half-open Python Unicode character offsets, per contract v1.

| Payload path | Supplied range | Quote length | Exact occurrences (start) |
| --- | --- | ---: | --- |
| `events[0].state_evidence` | `[218,258)` | 43 | 374 |
| `events[0].entities[0].evidence` | `[0,8)` | 8 | 18, 243 |
| `events[0].entities[1].evidence` | `[249,259)` | 11 | 406 |
| `events[0].entities[2].evidence` | `[299,311)` | 13 | 451 |
| `events[0].date_evidence` | `[193,205)` | 13 | 209 |
| `events[0].evidence[0]` | `[0,99)` | 100 | 0 |
| `events[0].evidence[1]` | `[218,347)` | 122 | 374 |
| `economics.favorable[0].evidence[0]` | `[218,347)` | 122 | 374 |

The second row satisfies the span-length check but fails exact source slicing.
Multiple differing displacements and length errors cannot be explained by a
single inclusive-end, UTF-8/UTF-16 or concatenated-fields conversion. Some
off-by-one values alone do not prove the model's internal counting strategy.

## Other conditions (latent, not production failure stage)

- **Dates:** normalized event date `2026-10-08` corresponds to the explicitly
  cited natural-language date, but not an ISO literal in that quote. Once child
  spans are valid, `ExtractedNewsEvent.factual_structure` would reject it with
  `event date not explicitly supported in ISO source form`. This is an
  intentionally narrow v1 policy, not proof of an invented calendar date.
  Announcement/publication datelines must still be distinguished from the date
  an acquisition completed; normalization alone does not establish event role.
- **Entities/registry:** entity index 2 assigns a product/platform name to
  ticker `MSFT`; an eligible MSFT company entry exists but that name is not a
  corporate name/alias. The identity guard would reject this. A product mention
  does not justify mapping it to a corporate/security subject. Other entities
  have names grounded in quotes and no security IDs/tickers; absent registry
  entries alone do not invalidate those unlinked named entities.
- **State/stage/negation:** `confirmed` / `announced`, no negation. Independent
  lexical inspection finds announcement support, no uncertainty/negation marker
  that would conflict with these labels. This is not exhaustive entailment.
- **Numbers/units/contradictions:** zero NumericClaim objects; those numeric
  rules do not explain this rejection. It does not certify all possible omitted
  quantities or contradictions. Digits inside a product name are not by
  themselves financial claims.
- **Economic discipline:** one favorable `reported_fact` with supplied evidence;
  no missing evidence list, inference-without-rationale or forbidden investment
  directive marker. Its quote is among the invalid spans. No accepted payload
  exists, and economic correctness/materiality is not independently certified.

## Cause classification

Primary: **model-generated citation/offset contract violations**, correctly
rejected by fail-closed validation. Exact quote text existing elsewhere cannot
justify accepting wrong coordinates, particularly with repeated mentions.

Secondary: unsupported product-to-security linking is a model/identity-contract
violation, not a reason to add a product to the corporate alias registry.
ISO-only dates expose a restrictiveness/usability limit worth future review.

There is no mismatched schema version or demonstrated wire incompatibility.
Structured Outputs covers the projected JSON shape, not Python after-validators
or source-dependent equality/registry/entailment checks. The prompt mentions
exact Unicode offsets; neither JSON Schema embeds cross-field span arithmetic
nor the current prompt explicitly explains the ISO-literal-only date rule.
This gap helps explain a structurally valid response failing local validation,
but is not evidence of a provider transport bug. One smoke cannot establish
model population reliability, semantic quality or relative model performance.

## Minimal generalizable proposal — NOT IMPLEMENTED

1. Keep strict source equality, half-open offsets and ambiguity rejection.
   Under a separately approved version, consider making the model select exact
   evidence text/IDs and assigning offsets deterministically only when a quote
   has one exact occurrence in its declared field. Never fuzzy-match, silently
   change evidence fields/revisions or choose the first repeated occurrence.
   Alternative: supply explicit span IDs/boundaries; do not rely on LLM character
   arithmetic. This requires contract/prompt/version review, not ad hoc repair.
2. Independently consider a narrowly versioned deterministic date policy for
   complete, unambiguous textual dates, explicit locale/year and cited date role.
   Reject ambiguous numeric/relative dates, and never substitute publication
   metadata automatically. A parsed date must agree with the claimed date.
   Retaining v1 with null/unknown dates is a valid conservative alternative.
3. Preserve corporate/security registry strictness. Product/platform mentions
   can remain unlinked; do not invent a ticker or expand aliases to pass this case.
4. A future diagnostic interface may emit safe stage/path/rule codes instead of
   only the generic error, without quotes/provider text/Pydantic input dumps.
   Keep end-user errors sanitized; observability does not authorize source leaks.

Any future changes need synthetic negatives (including ambiguous quotes/dates,
wrong event-date roles, unrelated tickers and fabricated evidence), versioned
configuration and separate quality review. This smoke is now development
diagnostic material, not an independent holdout for tuning those changes.
Do not rewrite or reclassify the original record or automatic `invalid_response`.

## Regression evidence and restrictions

`tests/unit/test_news_smoke_diagnostic_regressions.py` contains nine new synthetic
tests: inclusive ends, displaced but length-valid spans, field-local offsets,
Unicode codepoints, repeated-quote ambiguity, current ISO-date restriction,
null/literal ISO dates, product/security identity separation and valid abstention.
All nine pass under **unchanged validators**. Passing tests reproduce rejection
and control behavior; they do not constitute acceptance of a proposed algorithm.

No `.env` loading, provider calls, attempt/index/ledger writes, new inference,
official holdout, tuning, prompt/algorithm changes, retention bypass or 4C.3 work.
The original record and frozen artifacts remain unchanged; no licensed content
was copied into tests or this report. Expired original content must follow the
existing physical-cleanup procedure; this metadata-only diagnosis does not
extend its TTL or justify replay after expiry.

Final checks: **512 tests passed**, including the nine new regressions;
`python scripts/validate_data.py` and `python -m compileall -q src scripts`
passed. SHA-256 comparison confirms **2,804 diagnosis-scope files unchanged**,
including the original attempt and ledger, and **2,777 frozen files unchanged**
against the retained protected baseline. Only this metadata-only report and the
new synthetic test file were added; no production modules were edited.
