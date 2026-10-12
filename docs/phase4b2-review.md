# Phase 4B.2 — Targeted Semantic Improvements

Status: `implemented_pending_external_review`. Phase 4C remains not started.

## Diagnosis and implementation

See [initial diagnosis](phase4b2-diagnosis.md) and
[ADR-025](decisions/ADR-025-targeted-editorial-equivalence.md).
The productive Apple pair failed headline equality and similarity, not
candidates, entities or PIT. Headline cosine ablations: original 0.578947;
iPhone spacing alone 0.801002; demand equivalence alone 0.736842; terminal
Nikkei credit alone 0.612056. Together headlines are equal (cosine 1).
Global cosine remains 0.550365 because summaries differ.

Opt-in v1.1 accepts exact equivalent substantive headlines after these
normalizations, subject to entity/time/factual protections. It does not lower
thresholds or change exact-duplicate identity. Numerical generations and
state transitions remain guarded. No blocking or event redesign is justified.
Complete-link and budgets are unchanged. Original defaults/config remain v1;
new algorithms use `config/news_grouping_v1_1.yaml`. The schema stays v1.

## Offline comparison

| Sample | Candidate pairs (both) | v1 duplicate pairs/groups | v1.1 duplicate pairs/groups | Shared-event pairs (both) | v1.1 multinews clusters |
| --- | ---: | ---: | ---: | ---: | ---: |
| Original 200 | 3,789 | 0 / 0 | 0 / 0 | 0 | 0 |
| Extended 500 | 26,552 | 0 / 0 | 1 / 1 editorial | 0 | 1 |

No exact groups. The extended v1.1 distribution is 498 singletons and one
size-two cluster; original distributions are all singletons. The only changed
pair is the diagnosed development case, consistent with user AI-assisted
adjudication but still requiring external review for possible false positives.
More groups is not evidence of improved quality; no population metrics claimed.

Original snapshot identities reproduce exactly:

- 200: `00898f1ea1baad745335213906be0478f3788618891d463e61c6d242805924ae`
- 500: `85072aca40381289e0109b6e28769bc31886b2fc54442dbcc0511569360118d2`

New identities:

- 200: `e06acb63944f9997bef052cbb2a535dbba406008b0782a2e830c5cd1d7e93a9a`
- 500: `cc807dba9bb86452c534b195dacc26ad4c6e940862c3801201b760d963f7a49b`
- Parameters: `361ef0d3b5cdcfc0909ddf0a5f2c12e8b07952c454b3cb55fd0c776218ca3cd9`

Input/registry fingerprints match within each comparison. Full metadata is in
`data/reports/news/phase4b2_comparison.json`. Licensed evidence/new memberships,
snapshots and lineage remain in ignored `data/reports/news/phase4b2_local`.

## Evaluation and provenance

All original 36 pairs become development through `prior_review_role.json`
in the new tree; original files/labels/provenance are preserved. The locally
present aggregate evaluation reports 34 different, one editorial duplicate,
one uncertain. Original blind human fields remain blank: this AI-assisted
report must not be presented as independent human ground truth.

New review ID:
`1f954cabead53b8a1af255ef53aa0f07eb12bd8a9f65c073077a21f835465cf2`.
Forty real pairs, seed 4202, exclude 68 previously presented provider-ID pairs,
including all original 36; no synthetic development fixtures are reused.
Deterministic selection includes numerical conflicts, states, products,
companies, earnings and ambiguous identities. No additional proposed
exact/editorial/shared-event positives remain after exclusions; high-similarity
and financial-similarity strata are unavailable. This limitation is reported,
not hidden by replacing cases or tuning. Nine new fictional unlabeled cases
complement all nine requested scenarios; they are external-review prompts,
not regression oracles or supposedly human reference labels.

Give only `blind.json` to the real-case reviewer; keep technical predictions,
sampling categories and development diagnosis separate until adjudication.
Fill `human_label`, `human_rationale`, `reviewer`, `reviewed_at` (timezone-aware
ISO datetime). Use `uncertain` when headline-only evidence is insufficient;
summaries are omitted without provider-rights verification. All forty labels
must be attributed before metrics. Give `synthetic_supplement_blind.json`
(not the cue-bearing technical supplement) to a separate synthetic reviewer,
record reviewer/rationale/date and synthetic/AI-assisted/human provenance;
never pool its counts with real or population metrics. Coverage cues remain
outside the blind file and are not reference answers.
Uncertain real cases are excluded from conclusive metrics.

Algorithm/parameters/selection/predictions are frozen before review. New labels
cannot tune algorithms unless this set is retired to development first.
External adjudication is pending; current reference metrics are null.

## Reproduction and validation

```powershell
python scripts/run_phase4b2_offline.py --diagnose-only
python scripts/run_phase4b2_offline.py
python scripts/run_phase4b2_offline.py --evaluate-dir data/reports/news/phase4b2_local/reviews/1f954cabead53b8a1af255ef53aa0f07eb12bd8a9f65c073077a21f835465cf2
python -m pytest tests/unit/test_news_grouping_v1_1.py tests/unit/test_news_grouping.py tests/unit/test_news_semantic_review.py tests/integration/test_news_groups_pit.py tests/integration/test_phase4b2_offline.py
python -m pytest
python scripts/validate_data.py
python -m compileall -q src scripts
```

No dotenv/credential access or provider construction. Reruns preserve review
edits/snapshot bytes; changed evidence requires new identities. Both versions
are tested for future news/revisions/registry, strict/research, deterministic
candidates/order, budget, idempotence, complete-link and lineage. Specific
regressions reproduce the real false negative and adversarial facts/entities.

Executed validations: specific suite 66 passed; full suite 393 passed in
44.68 seconds; validate_data and compileall passed. The existing News Store
has 905 raw captures/revisions, 811 logical articles, zero bad hashes and zero
missing lineage. Original enrichment integrity covers four snapshots; the
separate new store validates two more. Two full offline runs reproduced the
same snapshots, comparisons and review identity. The real review evaluator
reports zero adjudicated, forty pending, metrics null.

Protected map: 2,777 original news/configuration, frozen reports/models,
features and targets; fingerprint
`42fde87be6765ddb2c1269360d8f16dc1a5d8ace2b9451208efa507a3b91c383`.
Every recorded file retains its bytes. Original snapshot IDs also reproduce.
No official Phase 3 TEST run or candidate change occurred. Git status cannot
run because installed git.exe is invalid for this Windows platform; index/
tracking verification is not claimed. Ignore patterns are inspected directly.

## Files and limitations

New: editorial-normalization module, v1.1 config, offline runner, specific unit
tests, unlabeled supplement, ADR-025, diagnosis, delivery and public comparison.
Updated: grouping dispatch, review sampling, old-review CLI role guard, PIT
integration parameterization, relevant docs and ignore rule. Local generated
evidence/snapshots/review stay ignored; original configs/evidence stay intact.

Lexical compatibility is not entailment; contextual facts/negation can escape
guards and conservative number/state equality can reduce recall. Shared-event
vocabulary, historical registry and independent real-positive coverage remain
limited. External review is required before claims of generalization or 4C.
