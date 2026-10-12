# Phase 4C.2: first smoke preparation — NOT EXECUTED

Status: `prepared_offline_not_executed`. This is not external semantic evaluation,
acceptance of 4C.2 or implementation of 4C.3. All interpretations remain
experimental, non-operational and disconnected from features/models/trading.
OpenAI Docs informed the versioned pricing and Responses transport correction;
see [ADR-029](decisions/ADR-029-cache-write-pricing-and-smoke-preflight.md).

## Verified profile and limitations

`config/news_interpretation.local.yaml` selects exactly `gpt-5.6-luna` via Responses:
strict JSON Schema, `reasoning: {effort: none}`, maximum output 2048, context
1,050,000, documented maximum input 922,000 and output capability 128,000.
No temperature, tools, retrieval, background mode, automatic repair or retry.
`service_tier: default` prevents inheriting a project's more expensive mode.

Official rates per million: ordinary input USD 0.20, cached reads USD 0.02,
cache writes USD 0.25, output USD 1.20. The profile only accepts input bounds
at or below 272,000; above that the model has different full-request prices.
The large context window is a model capability, not permission to use the
short-context rate for a million-token prompt. Local validity is explicitly
`[2026-10-12T19:23:26Z, 2026-10-13T00:00:00Z)`; this conservative deadline is
our re-verification policy, not an official promise that prices cannot change.
After expiry, re-check official documentation and version the replacement
configuration. Do not simply extend dates to bypass the guard.

Maximum one attempt, per-request AND per-run budget USD 0.05. Shared preflight
computes conservative UTF-8 wire bytes plus 256 framing tokens. For this request:
input bound 19,065, reservation USD 0.00722385 at the highest input rate plus
2048 output tokens. This is a conservative application estimate, not an invoice
guarantee or remotely verified token count. Missing telemetry retains the full
reservation; no fabricated zero cost. The CLI creates a fresh run per invocation:
do not repeat its command blindly, especially after an uncertain timeout.

## Selected existing Finnhub revision

- `revision_id`: `cf30928f3556c330851ab2423114f42ad8db6c2cb467b8367ee8e8b698b5bc12`.
- `provider_news_id`: `142727099`; source metadata Yahoo, text attributes the
  announcement to GLOBE NEWSWIRE. No link was retrieved or article downloaded.
- Selection: CyberFOX's acquisition of Optimize365, a concrete M&A event.
  Persisted headline plus 499-character summary identifies buyer, acquired
  company and economic/product rationale. Summary is truncated, not a full
  article: consideration, financing and other absent facts must remain unknown.
- Microsoft 365 is a product/platform reference. `MSFT` is a provider tag, not
  proof Microsoft is the acquirer, target or economically material protagonist.
- `published_at`: `2026-10-08T13:00:00Z`.
- `first_seen_at`, `available_at`, `ingested_at`:
  `2026-10-12T12:54:54.561149Z`.
- Cutoff: **`2026-10-12T13:17:53Z`**, also the availability of eligible registry
  inputs (11 entries). Strict builder confirms this is the latest eligible
  revision of the article; input availability equals cutoff, without proxies,
  future revisions or enrichment snapshots. No extra news was ingested.

The cutoff describes availability of source inputs, not availability of an LLM
interpretation on that historical date. Actual generation/validation/persistence
will be recorded when a separately authorized real inference occurs.
Successful abstention is allowed; no semantic output is promised or fabricated.

## Commands

From `C:\Nacho\modelo_inversiones`, offline preflight (safe to repeat):

```powershell
python scripts/run_phase4c2_news_smoke.py --config config/news_interpretation.local.yaml --model gpt-5.6-luna --budget-usd 0.05 --revision-id cf30928f3556c330851ab2423114f42ad8db6c2cb467b8367ee8e8b698b5bc12 --as-of 2026-10-12T13:17:53Z --validate-only
```

Expected: `validated_offline`, zero provider calls, zero persistence writes,
one attempt maximum, strict structured output and the reservation above.
Preparation found `OPENAI_API_KEY` absent from the process environment. This
does not inspect `.env` or invalidate any locally stored credential. Subsequent
ADR-030 adds centralized loading of the repository-root `.env` ONLY after
`--confirm-real-inference`, with `override=False`; existing shell values win.
Imports and `--validate-only` never load it. The provider client still reads
only the initialized environment and never prints the key. Never paste it
into YAML, CLI arguments, reports or a tracked file. Account model access,
billing balance and remote retention entitlements were NOT checked offline.

Real command, prepared only; **not run in this task**:

```powershell
python scripts/run_phase4c2_news_smoke.py --config config/news_interpretation.local.yaml --model gpt-5.6-luna --budget-usd 0.05 --revision-id cf30928f3556c330851ab2423114f42ad8db6c2cb467b8367ee8e8b698b5bc12 --as-of 2026-10-12T13:17:53Z --confirm-real-inference
```

Only execute after separate authorization, a fresh successful preflight and
confirmation that forwarding the limited licensed text is permitted. Retain
metadata-only CLI output; do not publish local attempt content. Exact cache
recovery costs zero and preserves generation, but does not create new evidence.

## Retention and physical cleanup (instructions only)

Local restricted attempts expire 24 hours after persistence; expired cache and
replay are rejected. TTL is NOT automatic physical deletion. No runtime content
exists from this preparation. The root `data/cache/*` is ignored by Git, as is
`.env`; protected news raw/processed/snapshots are not cleanup targets.

Remote: `store:false`, `background:false`, implicit prompt-cache minimum TTL
30 minutes. OpenAI may retain caches longer; default abuse-monitoring logs can
remain up to 30 days, with documented legal/security exceptions. Local cleanup
does not delete remote logs/caches and does not imply Zero Data Retention.

After a future smoke, stop writers and obtain local authorization to purge.
Inventory expired, hash-verified attempts without printing any content:

```powershell
python -c "from pathlib import Path; from datetime import datetime, timezone; import hashlib; from investment_system.agents.news_interpretation.persistence import ATTEMPT_ADAPTER; root=Path('data/cache/news_interpretation').resolve(); now=datetime.now(timezone.utc); [(print(p.name, r.expires_at.isoformat(), 'index='+hashlib.sha256(r.cache_key.encode()).hexdigest()+'.json')) for p in (root/'attempts').glob('*.json') if p.resolve().is_relative_to(root) for r in [ATTEMPT_ADAPTER.validate_json(p.read_text(encoding='utf-8'))] if r.record_id==p.stem and r.expires_at<=now]"
```

For each listed expired record, review its exact absolute attempt and index
paths under `C:\Nacho\modelo_inversiones\data\cache\news_interpretation`.
Confirm the index still points to that exact expired record (a newer attempt
can have replaced the pointer), and that neither path nor a parent is a link
outside the restricted root. Re-check expiry immediately before deletion.
Delete ONLY those individually verified files with PowerShell
`Remove-Item -LiteralPath '<exact verified absolute file path>'` (no recursive
deletion, wildcards, root-directory deletion or shell handoff). Preserve all
non-expired records, budget ledgers under `budgets` (contain reservations, not
licensed text), original Finnhub evidence, frozen phase artifacts and reports.
If an attempt is corrupt/unverifiable, stop and review it separately; never
broaden the deletion scope. This purge is not performed by preparation or CLI.

## Offline validation

New tests cover disjoint writes/reads, missing/malformed/overlapping telemetry,
conservative write-rate reservation, price-band/budget rejection, single-attempt
timeouts, mock Responses wire, immutable v2 persistence/replay/cache, version
separation and no-provider/no-persistence CLI preflight. Legacy 4C.1 and v1
runtime tests remain required, along with full pytest, validate_data and compileall.
Protected artifacts are compared byte-for-byte against a pre-edit SHA-256
inventory. No official holdout, model adjustment, real inference or 4C.3 work.

Executed on 2026-10-12:

- Focused runtime/CLI/cache-write suite: **60 passed**.
- `python -m pytest`: **483 passed** (offline networking guard enabled).
- `python scripts/validate_data.py`: passed, 905 raw captures/revisions,
  811 logical articles, zero bad hashes/missing lineage/duplicate records;
  four original enrichment snapshots valid.
- `python -m compileall -q src scripts`: passed.
- Original protected inventory: **2,777 files unchanged** against the pre-edit
  baseline. Additional comparison to the retained pre-4C.2 inventory:
  **2,849 evidence/history files unchanged**, including all 12 files of the
  two local v1.1 snapshots and frozen 4C.1 evaluation documents.
- Git executable is unavailable on this machine (invalid executable format).
  Read-only parsing of the existing v2 Git index confirms `.env` and runtime
  content are not tracked; `.gitignore` excludes both. No secrets were read.
- Offline preflight passed; runtime persistence tree remains absent.
