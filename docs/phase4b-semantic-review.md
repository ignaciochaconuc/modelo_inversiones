# Phase 4B.1 independent semantic review protocol

Original preparation status: `implemented_pending_external_review`. The tool
prepared external adjudication without assigning reference labels or approving
semantic quality. Final governance states are recorded below; 4C is not started.

## Formal closure update

Final 4B.1 status: `completed_ai_assisted_semantic_review`; 4B:
`completed_with_documented_limitations`; 4C: `not_started`.
The project owner's external review records 36 ChatGPT-assisted adjudications:
34 different, one editorial duplicate, one uncertain and one duplicate FN
subsequently used for development. This is not independent human ground truth
or population evaluation. Do not pool with the separate 40-case 4B.2 review.
The original 36 cases now have development/diagnostic provenance.
See [formal closure](phase4b-closure.md) for limitations and governance approval.

Pending-state observations and validations below are historical implementation
records, not the final governance state. Blank human fields and previous
reports are preserved; no reviewer or label is invented.

## Sampling and immutable prediction evidence

Phase 4B.2 provenance update: the original 36 cases were inspected in an
AI-assisted adjudication and now constitute development/diagnostic material,
not independent human ground truth. Original evidence and labels remain
unchanged; the new ignored role sidecar records this status. Use the disjoint
review described in `phase4b2-review.md` for the separate follow-up adjudication.

`scripts/prepare_phase4b_semantic_review.py` reads the existing strict pilot
snapshot and can reconstruct a bounded, balanced snapshot with up to 500
eligible articles under the **unchanged** 4B contracts, registry, thresholds and
algorithm. It retains the original cutoff. No requests, credentials or LLMs are
used. The original News Store and persisted 4B snapshots are not rewritten.

The audit enumerates pairs inside the frozen 48-hour window on these eligible
inputs. It reuses stored pair predictions where present. Additional pairs
outside the production candidate blocks are scored by the original classifier
and marked `audit_only_cross_block_score`. These extra scores are not reported
as pipeline candidate decisions. Actual duplicate-group and event-cluster
membership is preserved separately for subsequent evaluation of clustering.

Selection uses versioned SHA-256 case IDs from sorted revision identities.
Seed 42 drives hash-ranked ordering and a draw of eight random eligible pairs.
Ten strata are visited in deterministic round-robin order until 36 distinct
cases are selected. A case retains all matching strata. No quota is invented
for an empty stratum. The sampling-only definitions are:

| Category | Sampling cue |
|---|---|
| High similarity rejected | Frozen pair classifier says different; text cosine >= 0.85 |
| Near editorial threshold | Absolute distance from frozen 0.90 cosine threshold <= 0.05 |
| Near event threshold | Absolute distance from frozen 0.55 cosine threshold <= 0.05 |
| Same entity nearby | Shared resolved corporate identity inside the original time window |
| Different entities, similar text | Both resolved entity sets nonempty/disjoint; text cosine >= 0.40 |
| Earnings | Both texts contain earnings vocabulary from the unchanged algorithm |
| Other corporate event | Both texts contain other corporate-event vocabulary |
| Factual conflict cue | Different numeric/date or action token sets; no human factual conclusion implied |
| Ambiguity | At least one original entity link is ambiguous |
| Random eligible | Seeded eight-pair draw from the entire bounded eligible pool |

The 0.85/0.40/bandwidth values are audit sampling criteria, not new 4B grouping
thresholds. Two provider-ID pairs previously used as development examples in
the 4B pilot are excluded where present. If a selected case later guides an
algorithm change, this set must be reclassified as development; a new independent
evaluation must use cases not used in those decisions. Frozen synthetic 4B
examples are not reused as real adjudication cases.

## Local files and blinded adjudication

Restricted evidence lives only in the ignored folder:
`data/reports/news/phase4b_semantic_review/<review_id>/`.

- `blind.json`: article IDs/revisions, publication, first observation and verified
  availability, headline, source, original URL and provider tags. Human fields
  start empty. It contains no predictions, similarities, rejection reasons,
  resolved-entity judgments or sampling strata.
- `technical.json`: the same case IDs and content evidence, original entity
  links, scores, reasons, model parameters, actual group membership, source
  fingerprints and raw capture identities.
- `manifest.json`: frozen sample identity, pool/stratum counts and uncertainty
  limitations. This is technical material and should remain hidden from the
  adjudicator until labels are locked.
- `source_snapshot.json`: original or reconstructed causal input/evidence
  snapshot, stored locally so its complete lineage can be audited.
- `evaluation.json`: added when the evaluation script runs; pending review
  produces counts and `metrics: null`, not invented quality estimates.

Default evidence omits summaries because retention in the original store does
not establish redistribution/presentation permissions. After checking the
provider's local presentation rights, `--include-summaries` creates a separate
review identity with summaries. Do not publish either bundle. Original URLs may
help a reviewer obtain licensed context, but the web page may have changed:
judge the captured revision rather than silently replacing it with current text.

The writer restricts destinations to the ignored tree and never overwrites an
existing adjudication file. Evaluation checks original evidence fingerprints,
prediction integrity and matching case IDs. If a blind file was saved before
adjudication, rerunning generation preserves the edits.

## Exact reviewer procedure

1. Prepare the files:

   ```powershell
   python scripts/prepare_phase4b_semantic_review.py --size 36 --seed 42 --snapshot-articles 500
   ```

2. Give the external reviewer only `blind.json`. Do not show `technical.json`,
   the stratum counts or algorithm output before adjudication.
3. For every case, edit only `human_label`, `human_rationale`, `reviewer` and
   `reviewed_at`. Preserve IDs and all article evidence.
4. Choose exactly one label: `exact_duplicate`, `editorial_duplicate`,
   `shared_event`, `different` or `uncertain`. An exact duplicate repeats the
   same captured content; an editorial duplicate is substantially equivalent
   coverage; shared event has independent information about one concrete
   occurrence. Sharing company/date alone is insufficient. Use `uncertain`
   when the captured evidence cannot support a reliable distinction.
5. Supply a readable rationale, actual reviewer identity and actual review time
   in ISO 8601 with timezone, for example `2026-10-12T15:00:00-03:00` **only if
   that is the real review time**. The tool does not invent a reviewer or time.
6. Save valid UTF-8 JSON and lock labels before opening technical predictions.
7. Run:

   ```powershell
   python scripts/evaluate_phase4b_semantic_review.py --review-dir data/reports/news/phase4b_semantic_review/<review_id>
   ```

All cases, including `uncertain`, must be adjudicated before metrics are emitted.
Uncertain pairs appear in the confusion matrix and human-abstention frequency
but are excluded from precision/recall denominators. Metrics distinguish pair
classification from actual duplicate-group/event-cluster membership. They
include multiclass precision/recall/F1 and overlapping-stratum breakdowns.

This deliberately enriched difficult-case sample is not a random population
sample. Its precision/recall cannot be interpreted as market-wide accuracy.
Numeric/date conflicts and entity links are algorithm evidence, not a reference
truth. Human adjudication is still pending; no semantic conclusion has been
drawn from these 36 unlabelled cases.

## Publication and verification

The only publicable data artifact is
`data/reports/news/phase4b_semantic_review_summary.json`. It contains allow-listed
counts, SHA-256 fingerprints, methodology, categories, state and reproduction
command, with no headlines, summaries, URLs, raw payloads or human rationales.
Creation of this report does not publish anything to GitHub automatically.

## Prepared review and validation evidence

The final review identity is:
`8b446f52bcfcaac6f40541e7e9298db5371f60e68e584775fc4e6b492afe4ca0`.
Its `blind.json` and `technical.json` are in the ignored directory named by
that ID. All 36 cases have empty human fields. The evaluation script was run
only in pending mode: zero adjudications, 36 pending and `metrics: null`.

The source audit reconstruction contains 500 eligible articles at
`2026-10-12T13:17:53+00:00`, with snapshot identity
`85072aca40381289e0109b6e28769bc31886b2fc54442dbcc0511569360118d2`.
It retains the original frozen parameter fingerprint
`2bd98c953d60029e9af50d401a346aa1ce57772047a4af444c525881f8a7e978`.
The eligible pair pool contains 93,521 pairs. One of the two previously used
development pairs occurred in this bounded input universe and was excluded;
the other was absent. No category lacked candidates.

| Category | Pool count | Selected count |
|---|---:|---:|
| High similarity rejected | 1 | 1 |
| Near editorial threshold | 1 | 1 |
| Near event threshold | 18 | 7 |
| Same entity nearby | 26,551 | 12 |
| Different entities, similar text | 24 | 7 |
| Earnings | 3,589 | 5 |
| Other corporate event | 2,375 | 7 |
| Factual conflict cue | 40,091 | 18 |
| Ambiguity | 6,611 | 8 |
| Seeded random eligible draw | 8 | 4 |

Counts overlap and do not sum to 36. Four cases from the predefined random draw
were selected; the other strata intentionally enrich difficult examples. No
label, true-positive or false-positive conclusion is inferred from these counts.

Files created for implementation: `audit/news_semantic_review.py`,
`scripts/prepare_phase4b_semantic_review.py`,
`scripts/evaluate_phase4b_semantic_review.py`,
`tests/unit/test_news_semantic_review.py`,
`tests/integration/test_semantic_review_lineage.py` and this guide. Existing
changes are limited to `.gitignore`, README, ROADMAP, ARCHITECTURE and
PROJECT_SPEC documentation. No dependencies or 4A/4B contracts changed.

Verification executed:

- Specific tool tests: `12 passed in 2.02s`.
- Full suite: `354 passed in 42.73s`.
- `validate_data.py`: passed; original 905 records/captures, zero integrity
  errors, four unchanged original enrichment snapshots.
- `compileall -q src scripts`: passed.
- Repeated preparation reproduced review identity and preserved existing files.
- Actual blind/technical IDs match; all 144 human-field values are empty;
  zero captured headlines appear in the sanitized public report.
- Before/after hashing of 2,769 protected files was identical:
  `fffbb55f5a80da73a5e855278f19940cc3f2eb396577fc71701fbf443de39f49`.
  This covers Phase 3 artifacts, original 4A evidence, original 4B snapshots,
  all existing data modules and frozen configuration/registry files. No holdout
  was rerun.
- `.gitignore` explicitly ignores the whole local review tree, and tests verify
  this rule and restricted writer destinations. Native `git check-ignore`
  could not run because the installed `git.exe` is invalid for this platform;
  no claim is made that native Git validation succeeded.

An explicit root-anchored `.gitignore` rule ignores the entire local evidence
tree, including manifests, original snapshots and evaluation outputs.

```powershell
python -m pytest tests/unit/test_news_semantic_review.py tests/integration/test_semantic_review_lineage.py
python -m pytest
python scripts/validate_data.py
python -m compileall -q src scripts
```
