# CMA real panel v1 — candidate metadata, not an incorporated panel

Status: `candidate_metadata_prepared_pending_local_rights_review`.

The owner authorized controlled preparation of up to eight CMA/GOV.UK documents
in the attached instruction `00712481-571b-4a76-9d2f-634e2e154816`.
That attachment identifier is a file reference, not a conversation message ID.
No approval timestamp, message ID, signature or external adjudication is claimed.

## Outcome and boundary

Eight official-index candidates were examined at metadata level. The Content API
identifies CMA as a publishing organisation for each. All eight source pages
expose an OGL v3 link in their footer. Zero source documents were incorporated.
All eight are deferred from incorporation, not declared legally prohibited.

The page-level licence offer does not establish which particular body fields
contain third-party material or personal data. Those exclusions and evidence
sufficiency have not been examined by a local human. The owner's prohibition
on transferring source bodies to AI remains in force. Consequently this
preparation uses the expressly permitted fallback: a candidate/rights matrix
and documented blockers. It does not release a blind evidence bundle or create
semantic references, predictions, neutral security identities or a panel freeze.

Public titles, URLs, dates and organisation identifiers are metadata. The
preparing assistant has seen these metadata, not the document bodies. Future
reviewer exposure remains unknown and requires an actual declaration.

## Files

- `preparation-authority.json`: the real attached instruction, its SHA-256 and
  limited preparation scope; unknown approval timestamp/message ID remain null.
- `candidate-matrix.md`: operator-readable candidate titles, URLs and blockers.
- `candidate-manifest.json`: stable URL-derived candidate IDs and allowlisted
  Content API metadata. `first_published_at` supplies the publication date;
  the index's public timestamp is not substituted for first publication.
- `rights-matrix.json`: eight individual holds, licence candidate, applicable
  policy references and unresolved exclusions/modalities.
- `page-licence-checks.json`: exact page URLs, actual footer-check timestamps,
  observed licence URLs and SHA-256 of transient HTML, which was not retained.
  These hashes are not hashes of incorporated article evidence.
- `request-log.json`: four initial index searches and eight Content API metadata
  requests. Exact initial search timestamps were not captured and remain null.
  Eight additional HTML footer checks are logged in `page-licence-checks.json`:
  twenty public GOV.UK requests in total, no model-provider requests.
- `separation-audit.json`: URL identity searches of existing docs, evaluation
  instruments and tests. No matching URLs were detected. This is not proof of
  semantic originality, absence of paraphrases or absence of exposure.
- `exclusion-register.json`: eight provisional holds and their reasons.
- `historical-integrity-baseline.json`: before-preparation fingerprints for
  code, configurations, normative documents, evaluation instruments, tests and
  development-pilot records. Other data files have stat-only checks; expired
  model responses, restricted Finnhub text and credentials were not opened.
- `preparation-validation.json`: offline checks and their explicit limits.
- `artifact-hashes.json`: integrity inventory of this preparation, excluding
  itself to avoid a self-referential hash.

Local HTTP requests used only public GOV.UK endpoints. Full Content API payloads
and HTML existed transiently inside the local process; bodies, descriptions,
quotes and full payloads were neither persisted nor printed to the assistant.
There were no model-provider calls and no body transfer to an AI service.

## Temporal interpretation

`metadata_observed_at` and `metadata_ingested_at` are actual local observations
of metadata. They do not imply historical possession of source content.
`source_content_available_at`, `source_content_ingested_at`, evidence hash and
cutoff remain null because no evidence revision was incorporated. A future
authorized acquisition must record actual observation/incorporation and select
a cutoff at or after availability; it must not backdate to publication.
The remote revision identifiers are metadata only, not an exact content replay.

## Coverage and sampling limits

The eight candidates came from four small official-index searches (`merger`,
`cloud`, `licensing`, `platform`), deduplicated by URL. They are a convenience
shortlist, not a random sample or eight independent economic events. Multiple
documents may concern the same matter. No case has been assigned a direct,
indirect, contextual, ambiguous or negative reference label.

The suggested 3/1/2/1/1 coverage remains unverified. In particular no two
product/platform negatives, supported indirect relation or ambiguous identity
have been established. Any missing coverage must be reported, not manufactured.

## Next local action

A designated human custodian should inspect the eight source pages locally,
without pasting their bodies or screenshots into ChatGPT. Record per document:
exact authorised fields, explicit licence/attribution, third-party exclusions,
personal data, permitted human recipients, retention and evidence of clearance.
If scope is uncertain, keep the hold or obtain clarification from the rights
holder. OGL itself need not require additional permission when it demonstrably
covers the intended material; the missing item here is field-level verification,
not an assertion that every document requires a separate negotiated licence.

Only then may a separately versioned incorporation be prepared under the
owner's preparation scope. Do not overwrite this metadata-only snapshot or
silently turn an unknown into permission. A later explicit owner authorization
is required before external adjudication; AI transfer remains unauthorised.

No historical record, production contract, prompt, validator or official phase
state is changed. `integral_pilot_completed=false`,
`semantic_truth=not_assessed`, `factual_timing_rehabilitated=false`, Phase 4C.2
`implemented_pending_external_review`, Phase 4C.3 `not_started`.

## Recheck the preparation inventory offline

From the repository root (no network or credential loading):

```powershell
@'
import hashlib, json
from pathlib import Path
b = Path('evaluation/phase4c2_cma_real_panel_v1')
inventory = json.loads((b / 'artifact-hashes.json').read_text(encoding='utf-8'))
for record in inventory['files']:
    assert hashlib.sha256((b / record['path']).read_bytes()).hexdigest() == record['sha256']
manifest = json.loads((b / 'candidate-manifest.json').read_text(encoding='utf-8'))
assert len(manifest['candidates']) == 8
assert manifest['content_incorporated_count'] == 0
assert all(not c['incorporated'] and not c['evidence'] for c in manifest['candidates'])
print('Metadata inventory intact; rights and content eligibility remain pending')
'@ | python -B -
```

This checks metadata integrity only. It does not issue a legal clearance, decide
facts, certify independence or permit distribution of source content.

## Verification results

Eight in-memory deterministic/adversarial metadata checks passed. The existing
full pytest suite passed (1,188 tests, exit 0), with socket connections blocked,
bytecode disabled and pytest cacheprovider disabled. No tests/code were changed.
The post-suite historical check found 1,095 SHA-256 fingerprints unchanged and
3,254 other data-file size/mtime records unchanged. The latter is metadata
integrity, not cryptographic content verification. `scripts/validate_data.py`
was not run because it invokes integrity readers for the restricted original
Finnhub corpus; this task validates only the new metadata and its separation.
No code changed, so no compilation was necessary.
