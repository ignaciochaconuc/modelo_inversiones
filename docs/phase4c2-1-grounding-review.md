# Phase 4C.2.1 — Evidence Grounding Hardening

Status: **`implemented_pending_external_review`**. No real inference or provider
request in this task; 4C.3 remains `not_started`. The first rejected smoke is
preserved with its original ID, hashes, timestamps, outcome and ledger. It is
development diagnostic material, never an independent holdout or newly inferred
response. The frozen 4C.1 evaluation protocol remains unchanged.

## Contract comparison

| Concern | Historical flow | New opt-in flow |
| --- | --- | --- |
| Model output | `news-interpretation-v1`, quote + start/end | `news-quote-selection-v2`, evidence_id + quote only |
| Prompt | `news-interpretation-prompt-v1` | `news-interpretation-prompt-v2` |
| Resolution | Model proposes character arithmetic | `news-exact-quote-resolver-v1`, unique exact source match |
| Internal payload | v1 EvidenceSpan/domain payload | Same v1 payload, offsets generated deterministically |
| Result/replay | v1 result and ReplayEnvelope | `news-grounded-result-v2` / `news-grounded-replay-v2` |
| Runtime/attempt | Settings/attempts v1/v2 | Settings/attempt v3; transport/prices remain v2 |
| Raw provider text | Preserved | Preserved separately from selected/resolved/validated data |
| Evidence policy | Exact slices; explicit offsets can disambiguate repeats | Exact, unique matches; all citations primary-revision-only |
| Dates/registry/PIT | Original conservative rules | Same rules; no new date normalization or aliases |

`grounding.py` constructs quote-selection DTOs from the immutable v1 structural
fields without inheriting their semantic after-validators. This is a separately
versioned model-output contract, not a mutation of v1. Model-output/schema shape
is checked first; after deterministic resolution the original Pydantic and full
source-evidence validators run, then original replay/provenance checks run again.
Future changes to frozen v1 schemas require their own compatibility review.

## Resolution and auditable transformations

The declared evidence_id binds source revision, field, original text and
availability. Resolve only inside that exact eligible primary field. Search
overlapping occurrences as well as separated ones; do not search other fields,
normalize characters, pick a first repeat, rewrite quotes or repair meaning.
End = start + Python Unicode codepoint length; range `[start,end)`.

Each accepted selection preserves original response bytes in typed provider
provenance and stores a separate canonical selection hash, original content SHA,
resolved internal payload, quote/source hashes, evidence/revision/field and
offsets per model-field path. Completion timestamp is included. Failed resolution
does not create a partially accepted interpretation; rejected raw responses stay
under the same local restricted TTL, with safe diagnostic metadata.

Grounded replay recomputes from original provider content + original request,
configuration, versions and recorded timestamps. A changed quote, offset, trace,
source, fingerprint, result, diagnostic or timestamp breaks equality/identity.
Successful runtime attempts bind their exact expected wire preparation as well.
Original generation is preserved on cache hits; reconstruction never calls the
router. A new request's versioned key cannot hit an old v1/v2 entry.

Safe public diagnostics expose only `stage`, `field_path`, `rule`. For example:
`evidence_resolution / events[0].state_evidence / ambiguous_quote`.
Unknown model-supplied key names are replaced by `unknown_field`; no quote,
provider response, credential or Pydantic input/context dump is logged/reported.
Typed offsets/traces/payloads remain licensed local content, not public outputs.

## Dates, entities and risks

The prompt explicitly says to leave `event_date` AND `date_evidence` null unless
the cited text literally contains the correct ISO YYYY-MM-DD event date.
Textual dates are NOT normalized and publication metadata is NOT substituted.
Date support can be extended only via another reviewed version; current tests
intentionally keep textual-date claims rejected.

Product/platform references do not prove direct participation by the manufacturer.
The prompt instructs unresolved names rather than inferred manufacturer tickers.
Existing exact eligible registry-name/alias controls remain; no product aliases
are added. Literal grounding cannot establish economic participation/entailment
exhaustively; that limitation is not disguised as a new semantic certification.

Repeated quotations are intentionally rejected even when a model might have
intended one occurrence. Longer unique exact citations are allowed. Quotes
reused at multiple payload paths are fine if unique within their declared source
field. The same text in different fields is evaluated using its declared ID,
not an implicit cross-field search. Economic citations in v2 may not use another
revision, even eligible optional context; this is stricter than historical v1.
Other risks: quote selection can be irrelevant, schemas do not prove truth,
model variability remains, and longer citations may consume the output cap.
No retry or automatic repair is introduced to conceal invalid responses.

## Compatibility

Historical `schemas.py`, `replay.py`, `inputs.py`, fixtures and evaluation protocol
remain untouched. Persistence readers dispatch v1/v2/v3; no migration rewrites
an original file. The real first-smoke record remains
`3e354b82a8bf6aab2808dca0e770c7db74b29c4d947fcea7df2e0820b29c362d`,
with file SHA `fb73e309073f6efd1ffc14cfe71de5f2b34ab771380906e98ab0b9bb7ab2fd24`.
Its content is not fed to the new resolver as a fabricated new LLM response.
Protected histories, original profile and model defaults stay unchanged.

The existing CLI now reads either explicit runtime profile; its original v2
profile is not silently replaced. All provider/model, budget/reservation,
cost/usage, retention, authorization and environment-loading guards still apply.
`--validate-only` remains credential-free, with zero calls/persistence writes.

## Regression scope

New fictional fixtures test unique/missing/repeated/overlapping quotes, Unicode
and forbidden normalization, declared fields, wrong revisions (also economics),
model-supplied offsets, trace/offset tampering, shape-valid but ungrounded output,
products/incorrect tickers/unresolved identities, null/ISO/text dates, rumor,
negation, numbers/units, abstention, JSON failures and sanitized diagnostics.
Runtime tests cover immutable original-response persistence, exact replay/cache,
costs on rejected attempts, no retries, TTL, old replay/attempt identities,
version isolation, PIT/future invariance and offline CLI control paths.
These are development structural regressions, NOT independent semantic labels
or a population-quality evaluation. Follow the frozen 4C.1 evaluation protocol
before quality/model claims; do not tune on independent evaluation data.

## Second real smoke instructions — not executed

Use `config/news_interpretation.grounded.local.yaml`, a separate opt-in v3 profile
for the previously selected `gpt-5.6-luna`. It reuses the existing documented
capability/pricing attestation, without any online verification in this task.
Validity ends **2026-10-13T00:00:00Z**. If expired, reverify separately under
authorization and version the replacement; do not widen dates to bypass guards.
Maximum output 2048, reasoning none, one attempt, request/run USD 0.05.

The existing source revision/cutoff may be reused as a **development smoke**,
not as new independent evidence. Do NOT recover/modify the first rejected model
output and label it a new inference. A later real call must produce its own new
provider response/generation/attempt/ledger under the new prompt/profile/key.

First run offline preflight:

```powershell
python scripts/run_phase4c2_news_smoke.py --config config/news_interpretation.grounded.local.yaml --model gpt-5.6-luna --budget-usd 0.05 --revision-id cf30928f3556c330851ab2423114f42ad8db6c2cb467b8367ee8e8b698b5bc12 --as-of 2026-10-12T13:17:53Z --validate-only
```

This task's preflight passed: input upper bound **19,383**, maximum reservation
**USD 0.00730335**, strict output `news-quote-selection-v2`, zero calls and
zero persistence writes. These are conservative local estimates, not invoice
guarantees. API-key validity/account access cannot be verified offline.

Only after separate authorization, valid pricing/preflight and licensed-text
transfer/retention approval, the real command is:

```powershell
python scripts/run_phase4c2_news_smoke.py --config config/news_interpretation.grounded.local.yaml --model gpt-5.6-luna --budget-usd 0.05 --revision-id cf30928f3556c330851ab2423114f42ad8db6c2cb467b8367ee8e8b698b5bc12 --as-of 2026-10-12T13:17:53Z --confirm-real-inference
```

The real branch loads only repository-root `.env`, `override=False`, after the
confirmation flag. Keep keys out of YAML/logs/reports/arguments/Git. Do not
repeat the command blindly after a timeout. A valid abstention is allowed; no
promise that the second response will be accepted or semantically correct.

Original and new content expiry remains enforced. Follow the existing
`docs/phase4c2-smoke-preparation.md` cleanup instructions; neither quote resolution
nor this task extends TTL, deletes historical evidence or changes remote
retention. Original provider-content records are never copied into tests/docs.

## Final offline validation

- `python -m pytest`: **548 passed**; the new grounding file contributes
  **36 passed** synthetic regressions (also rerun separately).
- `python scripts/validate_data.py`: passed; 905 raw captures/revisions,
  811 logical articles, zero bad hashes/missing lineage/duplicate records,
  four original enrichment snapshots valid.
- `python -m compileall -q src scripts`: passed.
- SHA-256 inventory: **2,842 pre-existing data/config files unchanged**,
  including frozen Phase 3, 4A/4B evidence, the first smoke attempt and ledger.
  Original v1 schemas/replay/inputs and 4C.1 protocol/review/fixtures unchanged.
- The first smoke remains readable as attempt v2 with the same canonical
  record ID and file SHA, outcome `invalid_response`; no migration/new inference.
- Opt-in preflight passed with zero provider calls/persistence writes and no
  dotenv bootstrap. No prices/capabilities were refreshed via external requests.

Added: grounding module, synthetic test file, separate grounded local profile,
ADR-031 and this review. Updated: runtime schemas/service/persistence, smoke CLI,
ADR index, README, PROJECT_SPEC, ARCHITECTURE and ROADMAP. Existing profiles,
provider clients, router, domain validators and historical reports unchanged.
