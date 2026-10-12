# ADR-030: Explicit repository-bound CLI environment bootstrap

## Status

Accepted for the requested credential-loading correction. No provider calls or
smoke execution authorized. Phase 4C.3 remains `not_started`. ADR-028/029 remain
historical; this decision extends their environment-only provider boundary.

## Decision

`investment_system.core.environment.load_repository_environment()` is the only
dotenv bootstrap. It resolves the repository root from its module location, not
cwd or dotenv's upward search, and loads exactly `<repository-root>/.env`.
No alternate dotenv path is accepted; symlinks are rejected. Explicit boolean
real-operation authorization is required before filesystem access. Missing file
is allowed for system-only deployments. `override=False` preserves existing
environment variables, including deliberately empty values. Interpolation is
disabled so a secret cannot expand into an unrelated configuration variable.

Imports, `load_settings`, `load_news_settings`, tests, `--validate-only`,
`--dry-run` and `--skip-download` do not bootstrap secrets. Offline tests isolate
the helper root to temporary directories containing only synthetic test values.

The smoke retains `--confirm-real-inference`, mutually exclusive offline mode,
model/pricing/PIT/budget/reservation guards and one-attempt policy. Only its real
branch bootstraps before checking the key. Five other external CLI entrypoints
require `--confirm-real-requests` before bootstrap or workflow construction:
Finnhub pilot, market ingestion, provider-symbol diagnosis, real-data pilot and
full-universe build. Supplying a key alone is not authorization. Download-skip
and dry-run branches never bootstrap, even if confirmation is supplied.

The Finnhub key helper no longer accepts an arbitrary dotenv path. No provider,
agent, router, pricing schedule or interpretation contract loads dotenv.
Future CLI reuse this bootstrap at the authorization boundary; future agents
use their existing routed provider clients and already initialized environment.

Credentials are not returned by the bootstrap or written to YAML/reports/logs.
Bootstrap errors have fixed codes with neither cause nor exception context.
CLI boundaries suppress third-party exception bodies. Finnhub error reports
use a fixed code, logging redacts process API keys (including exception text),
Tiingo report errors redact before truncation, and symbol-diagnostic output is
redacted. `.env` stays ignored and untracked; `.env.example` remains placeholders.
These measures do not authorize forwarding keys in source text or CLI arguments.

## Verification and limits

Offline tests exercise anchored path, priority, missing file, no interpolation,
authorization, imports/YAML loaders, offline branches, safe exceptions/logs/
report errors and authorized synthetic bootstrap with no provider construction.
No real credentials are read during tests. Existing authorization and budget
tests remain required. This is not a secret vault or runtime authorization
service: the CLI owns user consent, the loader enforces the explicit gate, and
inference still passes through the existing router/budget controls.
