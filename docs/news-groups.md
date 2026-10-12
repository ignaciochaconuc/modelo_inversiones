# Phase 4B usage and review

Status: `implemented_pending_external_review`.

Configuration is separate from frozen Phase 3 configuration:
`config/news_grouping.yaml` and `config/news_entities.yaml`. The registry is
partial and dated; it covers the five news-pilot tickers, Alphabet's two share
classes, Meta's name/ticker transitions, and ambiguous short symbols T/V/C.
See ADR-024 for temporal policy, thresholds, lexical rules and limitations.

```python
from datetime import datetime
from investment_system.data.news_entities import load_entity_registry
from investment_system.data.news_grouping import build_news_groups_as_of, load_grouping_parameters
from investment_system.data.storage.news_store import NewsStore
from investment_system.data.storage.news_enrichment_store import NewsEnrichmentStore

news = NewsStore("data/raw", "data/processed")
snapshot = build_news_groups_as_of(
    news, datetime.fromisoformat("2026-10-12T13:17:53+00:00"),
    load_entity_registry(), load_grouping_parameters(),
    reconstruction_policy="deterministic_reconstruction_v1",
    max_articles=200,
    sample_strategy="provider_ticker_round_robin",
)
output = NewsEnrichmentStore("data/processed")
output.write(snapshot)
lineage = output.lineage(snapshot.snapshot_id, snapshot.inputs[0].revision_id, news)
```

The strict API filters available revisions before constructing its text blocks.
A historical reconstruction is a deterministic calculation from causal inputs,
not evidence that enrichment was originally observed at that time. Research
requires `mode=NewsQueryMode.HISTORICAL_RESEARCH` and explicit
`allow_historical_proxy=True` and/or `allow_retrospective_registry=True`; its
results retain uncertainty markers and cannot be passed off as strict evidence.

Reproduce the controlled local pilot without provider calls:

```powershell
python scripts/run_phase4b_news_pilot.py --as-of 2026-10-12T13:17:53+00:00 --max-articles 200
python -m pytest tests/unit/test_news_grouping.py tests/integration/test_news_groups_pit.py
python -m pytest
python scripts/validate_data.py
python -m compileall -q src scripts
```

The report is `data/reports/news/phase4b_pilot.json`. It records the full revision
audit, sample policy, two temporal modes, output identities, registry coverage,
labelled diagnostics, false positives/negatives and remaining review limitations.
The pair dataset has eight development and eight frozen diagnostic pairs; a
separate eight-case entity dataset measures scenario accuracy and abstention.
These labels are agent-authored with independent semantic rationales and remain
pending human adjudication.
Input identities/revisions and all links remain available in snapshot Parquet
tables. The public report contains no copied full provider article content.
The controlled sample takes turns between first provider ticker labels, using
only revisions already eligible at the cutoff. The final 200-record local sample
covers AAPL, MSFT, NVDA, JPM and XOM with 40 records each. This is a diagnostic
sample, not a representative random sample.

Entity linking is evidence attribution: a provider tag is not proof that an
article centrally concerns that company. Alias matches may identify a parent
company from a brand name without resolving legal subsidiary identity. Names
can remain ambiguous; coverage and abstention counts are not calibrated
accuracy. AAPL/MSFT/NVDA/JPM/XOM articles captured on 2026-10-12 are only strictly
eligible from their locally observed revision availability, irrespective of
earlier publication dates.
