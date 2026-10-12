# Phase 4B implementation evidence

Final status: `completed_with_documented_limitations`. No Phase 4C implementation.

External review authorizes technical closure, not exhaustive semantic
certification. See [formal closure](phase4b-closure.md) for separate AI-assisted
results, limitations and final states. v1 stays reproducible/default; v1.1 is
an opt-in future-integration candidate. Evidence below records the original
implementation, not a newly executed pilot.

## Artifacts and versions

- Contracts: `src/investment_system/data/schemas/news_enrichment.py` (`news-enrichment-v1`).
- Resolution: `src/investment_system/data/news_entities.py` (`entity-resolver-v1`).
- Grouping: `src/investment_system/data/news_grouping.py` (`news-groups-v1`, `unicode-word-bigram-v1`).
- Evaluation: `src/investment_system/data/news_evaluation.py`.
- Storage: `src/investment_system/data/storage/news_enrichment_store.py`.
- Configuration: `config/news_entities.yaml`, `config/news_grouping.yaml`.
- Offline pilot: `scripts/run_phase4b_news_pilot.py`.
- Labels: `tests/fixtures/news_pairs_v1.json`, `tests/fixtures/news_entity_cases_v1.json`.
- Tests: `tests/unit/test_news_grouping.py`, `tests/integration/test_news_groups_pit.py`.
- Methodology: ADR-024 and `docs/news-groups.md`.

Existing changes are limited to `scripts/validate_data.py` and documentation:
README, ARCHITECTURE, PROJECT_SPEC, ROADMAP and the ADR index. The 4A adapter,
contracts and store are unchanged. No new dependencies were introduced.

## Offline pilot

Command:

```powershell
python scripts/run_phase4b_news_pilot.py --as-of 2026-10-12T13:17:53+00:00 --max-articles 200
```

The full report is `data/reports/news/phase4b_pilot.json`. No network requests.

- Original data: 905 revisions, 811 logical articles, 84 multi-version articles.
- Extra rows: 94, all due solely to `direct_tickers` differences under the 4A hash contract.
- Controlled sample: 200 current eligible revisions, 40 each AAPL/MSFT/NVDA/JPM/XOM.
- Candidates: 3,789; exact groups 0; editorial groups 0; multi-article event groups 0.
- Event partition: 200 singletons, preserving every input.
- At least one entity per sampled article; 7 articles have an ambiguous security link.
- Links: 352 resolved, 9 ambiguous-security and 2 unresolved (an article may have several evidence links).
- Registry universe coverage: 11/101 current development tickers.
- Rebuild: identical snapshot ID; all 200 selected articles have verified raw lineage.

Strict snapshot:
`00898f1ea1baad745335213906be0478f3788618891d463e61c6d242805924ae`.

Research snapshot:
`a96fa7fb0f83bdae1d54361a70ab82ffb64cd393638670c01680bbc43ca9f265`.

Input fingerprint:
`3aeb2859d805d5b63425a3d6d31731fbb6527f10bb7409f5ffb8981e19099aaf`.

Eligible registry fingerprint:
`bca49c249e61d160b400cde92ef266ff080ea6388ca6b4df68d9624341a2a7d3`.

Parameter fingerprint:
`2bd98c953d60029e9af50d401a346aa1ce57772047a4af444c525881f8a7e978`.

Outputs are local under
`data/processed/news_enrichment/news-enrichment-v1/<snapshot_id>/`.
Two additional final-algorithm prefix-sample snapshots remain as valid diagnostic
evidence. Provisional implementation snapshots were moved recoverably into
`data/reports/news/phase4b_provisional_snapshots`; they are not final pilot outputs.

## Labelled diagnostics and error analysis

Eight development pairs and eight frozen diagnostic pairs each yield duplicate
precision/recall/F1 1.0 (two true positives, zero false positives/negatives).
Same-event precision is 1.0, recall 2/3 and F1 0.8, with one differently worded
event missed per partition. No thresholds were adjusted from those frozen
diagnostic results. Development-only threshold comparisons are in the report.

Eight additional synthetic entity cases yield scenario accuracy 1.0, resolved
entity coverage 5/8, three abstentions and one security ambiguity. This is not
calibrated population accuracy. Historical ticker/name and future-knowledge
cases are covered separately by regression tests.

Two real high-similarity market recap updates (IDs 142733043/142736500 and
142706903/142704791) were qualitatively reviewed as development negatives. They
demonstrate why added headline facts and omnibus coverage cannot be merged from
summary similarity alone. The final rule abstains. Labels and reviews were
authored by the implementing agent with explicit rationales; independent human
adjudication is still required. No protected full article text is published.

The absence of groups in the final real sample does not prove that those articles
contain no shared events. The algorithm deliberately favors precision and will
miss paraphrases, evolving stories and events without lexical anchors. More
independent labelled coverage is needed before broad use.

## Verification performed

- Specific Phase 4B tests: `16 passed in 1.37s`.
- Full `python -m pytest`: `342 passed in 31.21s`.
- `python scripts/validate_data.py`: passed; 905 original raw/normalized records,
  no hash/lineage/duplicate errors; four valid final-algorithm snapshots.
- `python -m compileall -q src scripts`: passed.
- Regression cases cover cutoff, later revisions/news, future registry releases,
  DST, proxies, order independence, exact/near/event distinctions, adversarial
  facts, aliases, ambiguous tickers/classes, temporal identity, lineage,
  preservation, deterministic sampling, rebuild and idempotence.

Before/after SHA-256 comparison covered 2,702 files: all Phase 3 model artifacts,
the four frozen snapshot configuration files, and all original Phase 4A raw and
normalized evidence. Both aggregate hashes were:
`16b2817614f2e7f3bf2e2925119a17e4ac701dd6b99a530394f5100b0a8e26de`.
No holdout run or predictive selection was performed. Frozen candidate/protocol
fingerprints and official result artifacts remain byte-identical.
