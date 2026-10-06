"""Diagnose a Tiingo symbol without persisting or changing market data."""
import argparse
from datetime import date
import json
import os

from investment_system.core.config import load_settings
from investment_system.data.provider_symbols import load_provider_symbols
from investment_system.data.sources.tiingo import TiingoEODDataSource


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    parser.add_argument("--start", type=date.fromisoformat, default=date(2009, 1, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date.today())
    args = parser.parse_args()
    settings = load_settings()
    key = os.getenv("TIINGO_API_KEY")
    if not key:
        raise SystemExit("TIINGO_API_KEY is not set")
    source = TiingoEODDataSource(
        key,
        base_url=settings.providers.tiingo.base_url,
        symbol_aliases=load_provider_symbols(),
    )
    try:
        print(json.dumps(source.diagnose_symbol(args.ticker, args.start, args.end), indent=2, default=str))
    finally:
        source.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
