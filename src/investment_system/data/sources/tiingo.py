"""Tiingo EOD adapter. Provider-specific field names must not escape this module."""
from collections.abc import Callable
from datetime import date, datetime, time, timezone
import re
from zoneinfo import ZoneInfo

import httpx

from investment_system.core.exceptions import DataSourceError, DataSourceRateLimitError
from investment_system.data.schemas.market import MarketBar
from investment_system.data.sources.base import BaseDataSource

_TICKER_PATTERN = re.compile(r"^[A-Z0-9.-]+$")

def _parse_clock(value: str) -> time:
    try:
        return time.fromisoformat(value)
    except ValueError as error:
        raise ValueError(f"invalid clock time: {value!r}") from error

class TiingoEODDataSource(BaseDataSource):
    """Synchronous Tiingo EOD client with normalized internal output."""

    provider = "tiingo"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.tiingo.com/tiingo/daily",
        market_timezone: str = "America/New_York",
        market_close_time: str = "16:00",
        assumed_available_time: str = "20:00",
        timeout_seconds: float = 20,
        schema_version: str = "1",
        client: httpx.Client | None = None,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("TIINGO_API_KEY is required")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timezone = ZoneInfo(market_timezone)
        self._close_time = _parse_clock(market_close_time)
        self._available_time = _parse_clock(assumed_available_time)
        self._timeout = timeout_seconds
        self._schema_version = schema_version
        self._client = client or httpx.Client()
        self._owns_client = client is None
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def fetch_daily_bars(self, ticker: str, start_date: date, end_date: date) -> list[MarketBar]:
        ticker = ticker.strip().upper()
        if not _TICKER_PATTERN.fullmatch(ticker):
            raise ValueError(f"invalid ticker: {ticker!r}")
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")
        try:
            response = self._client.get(
                f"{self._base_url}/{ticker}/prices",
                params={"startDate": start_date.isoformat(), "endDate": end_date.isoformat(), "resampleFreq": "daily"},
                headers={"Authorization": f"Token {self._api_key}", "Accept": "application/json"},
                timeout=self._timeout,
            )
        except httpx.HTTPError as error:
            raise DataSourceError(f"Tiingo request failed for {ticker}: {type(error).__name__}") from error
        if response.status_code == 429:
            raise DataSourceRateLimitError(f"Tiingo rate limit reached for {ticker}; retry later")
        if response.is_error:
            raise DataSourceError(f"Tiingo HTTP {response.status_code} for {ticker}")
        try:
            payload = response.json()
        except ValueError as error:
            raise DataSourceError(f"Tiingo returned invalid JSON for {ticker}") from error
        if not isinstance(payload, list):
            raise DataSourceError(f"Tiingo returned an invalid payload for {ticker}: expected a list")
        ingested_at = self._clock()
        if ingested_at.tzinfo is None:
            raise ValueError("ingestion clock must return a timezone-aware datetime")
        return [self._parse_bar(ticker, item, ingested_at) for item in payload]

    def _parse_bar(self, ticker: str, item: object, ingested_at: datetime) -> MarketBar:
        if not isinstance(item, dict):
            raise DataSourceError(f"Tiingo returned a non-object bar for {ticker}")
        required = ("date", "open", "high", "low", "close", "volume")
        missing = [field for field in required if item.get(field) is None]
        if missing:
            raise DataSourceError(f"Tiingo bar for {ticker} is missing required fields: {missing}")
        try:
            trading_date = datetime.fromisoformat(str(item["date"]).replace("Z", "+00:00")).date()
            observed_at = datetime.combine(trading_date, self._close_time, self._timezone)
            available_at = datetime.combine(trading_date, self._available_time, self._timezone)
            return MarketBar(
                ticker=ticker,
                trading_date=trading_date,
                provider=self.provider,
                schema_version=self._schema_version,
                open=item["open"], high=item["high"], low=item["low"], close=item["close"], volume=item["volume"],
                adjusted_open=item.get("adjOpen"), adjusted_high=item.get("adjHigh"), adjusted_low=item.get("adjLow"),
                adjusted_close=item.get("adjClose"), adjusted_volume=item.get("adjVolume"),
                split_factor=item.get("splitFactor") or 1.0,
                dividend_cash=item.get("divCash") or 0.0,
                observed_at=observed_at,
                published_at=None,
                available_at=available_at,
                ingested_at=ingested_at,
            )
        except (TypeError, ValueError) as error:
            raise DataSourceError(f"invalid Tiingo bar for {ticker}: {error}") from error

    def close(self) -> None:
        if self._owns_client:
            self._client.close()

    def __enter__(self) -> "TiingoEODDataSource":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
