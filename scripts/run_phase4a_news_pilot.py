"""Run the reduced Phase 4A Finnhub infrastructure pilot or record its blocker."""
from __future__ import annotations

import argparse
from datetime import date, datetime, timedelta, timezone
import json
import os
from pathlib import Path
from typing import Any

from investment_system.core.config import load_news_settings, load_settings
from investment_system.core.reproducibility import git_metadata
from investment_system.data.news_ingestion import NewsIngestionService
from investment_system.data.schemas.news import NewsQueryMode
from investment_system.data.sources.finnhub_news import FinnhubNewsProvider
from investment_system.data.sources.news import NewsFetchRequest, NewsIngestionPolicy
from investment_system.data.storage.news_store import NewsStore

PILOT_TICKERS = ("AAPL", "MSFT", "NVDA", "JPM", "XOM")
DEFAULT_REPORT = Path("data/reports/news/phase4a_pilot.json")


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"invalid date: {value}") from error


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description="Run the reduced Phase 4A news pilot")
    result.add_argument("--start", type=parse_date)
    result.add_argument("--end", type=parse_date)
    result.add_argument("--tickers", nargs="+", default=list(PILOT_TICKERS))
    result.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    result.add_argument(
        "--allow-published-at-proxy", action="store_true",
        help="historical research only; strict PIT still excludes proxy records",
    )
    return result


def write_report(path: Path, report: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp.json")
    temporary.write_text(json.dumps(report, indent=2, sort_keys=True, default=str), encoding="utf-8")
    temporary.replace(path)


def blocked_report(args: argparse.Namespace, reason: str) -> dict[str, Any]:
    return {
        "report_version": "phase4a-news-pilot-v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "blocked_no_provider_credentials",
        "provider": "finnhub",
        "requested_tickers": args.tickers,
        "requested_window": {"start": str(args.start), "end": str(args.end)},
        "blocker": reason,
        "real_requests_made": 0,
        "real_responses_received": 0,
        "news_captured": 0,
        "limitations": [
            "No FINNHUB_API_KEY was available; no live or historical provider evidence was fabricated.",
            "Historical depth, timestamp quality, plan entitlements and retention/redistribution rights remain unverified.",
            "Finnhub publication timestamps are not treated as observed availability in strict PIT mode.",
        ],
        "git": git_metadata(),
    }


def main() -> int:
    args = parser().parse_args()
    today = datetime.now(timezone.utc).date()
    args.end = args.end or (today - timedelta(days=1))
    args.start = args.start or (args.end - timedelta(days=4))
    api_key = os.getenv("FINNHUB_API_KEY")
    if not api_key:
        report = blocked_report(args, "FINNHUB_API_KEY is not configured")
        write_report(args.report, report)
        print(json.dumps({"status": report["status"], "report": str(args.report)}))
        return 2

    settings = load_settings()
    news_settings = load_news_settings()
    provider_settings = news_settings.provider
    store = NewsStore(
        settings.paths.raw, settings.paths.processed,
        schema_version=news_settings.schema_version,
        normalizer_version=news_settings.normalizer_version,
    )
    policy = NewsIngestionPolicy(
        mode="historical_backfill",
        allow_published_at_proxy=args.allow_published_at_proxy,
    )
    provider = FinnhubNewsProvider(
        api_key, base_url=provider_settings.base_url,
        timeout_seconds=provider_settings.timeout_seconds,
        max_retries=provider_settings.max_retries,
        retry_backoff_seconds=provider_settings.retry_backoff_seconds,
    )
    request = NewsFetchRequest(tuple(args.tickers), args.start, args.end)
    service = NewsIngestionService(provider, store, policy)
    errors: list[str] = []
    try:
        items = provider.fetch_news(request)
        first = service.ingest_items(items)
        second = service.ingest_items(items)
    except Exception as error:  # report provider/runtime failures without hiding their type
        errors.append(f"{type(error).__name__}: {error}")
        report = blocked_report(args, errors[0])
        report["status"] = "blocked_provider_error"
        write_report(args.report, report)
        print(json.dumps({"status": report["status"], "report": str(args.report)}))
        return 3
    finally:
        provider.close()

    records = store.read_records()
    now = datetime.now(timezone.utc)
    strict = store.query_as_of(now, mode=NewsQueryMode.STRICT)
    research = store.query_as_of(
        now, mode=NewsQueryMode.HISTORICAL_RESEARCH,
        allow_historical_proxy=args.allow_published_at_proxy,
    )
    integrity = store.validate_integrity()
    published = [record for record in records if record.published_at is not None]
    report = {
        "report_version": "phase4a-news-pilot-v1",
        "generated_at": now.isoformat(),
        "status": "completed_pending_external_review",
        "provider": "finnhub",
        "provider_configuration": {
            "base_url": provider_settings.base_url,
            "timeout_seconds": provider_settings.timeout_seconds,
            "max_retries": provider_settings.max_retries,
            "credentials_present": True,
        },
        "window": {"start": args.start.isoformat(), "end": args.end.isoformat()},
        "tickers": list(request.tickers),
        "requests_made": len(request.tickers),
        "responses_received": len(request.tickers),
        "news_captured": len(items),
        "new_raw_captures": first.new_raw_captures,
        "unique_logical_articles": integrity["logical_articles"],
        "normalized_revisions": integrity["normalized_records"],
        "idempotency_second_pass_new_revisions": second.new_normalized_revisions,
        "timestamp_coverage": {
            "published_at": len(published),
            "available_at": len(records),
            "first_seen_at": len(records),
            "published_at_ratio": (len(published) / len(records)) if records else None,
        },
        "direct_ticker_coverage": {
            "records_with_direct_tickers": sum(bool(record.direct_tickers) for record in records),
            "ratio": (sum(bool(record.direct_tickers) for record in records) / len(records)) if records else None,
        },
        "temporal_distribution": {
            "earliest_published_at": min((record.published_at for record in published), default=None),
            "latest_published_at": max((record.published_at for record in published), default=None),
            "earliest_first_seen_at": min((record.first_seen_at for record in records), default=None),
            "latest_first_seen_at": max((record.first_seen_at for record in records), default=None),
        },
        "strict_pit_records_at_report_time": len(strict),
        "historical_research_records_at_report_time": len(research),
        "integrity": integrity,
        "hash_validation_passed": not integrity["bad_raw_hashes"],
        "lineage_validation_passed": not integrity["missing_lineage"],
        "pit_validation_passed": all(record.available_at <= now for record in strict),
        "errors": errors,
        "limitations": [
            "The provider's published timestamp is not proof of local availability.",
            "Historical availability proxies are research-only and excluded from strict PIT queries.",
            "Plan-specific historical coverage and retention/redistribution rights require external review.",
            "The pilot validates ingestion infrastructure, not predictive utility or alpha.",
        ],
        "git": git_metadata(),
    }
    write_report(args.report, report)
    print(json.dumps({"status": report["status"], "report": str(args.report), "news": len(items)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
