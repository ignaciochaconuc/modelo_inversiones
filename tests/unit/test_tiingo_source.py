from datetime import date, datetime, timezone
import httpx
import pytest

from investment_system.core.exceptions import DataSourceError, DataSourceRateLimitError
from investment_system.data.sources.tiingo import TiingoEODDataSource

NOW = datetime(2025, 1, 3, 1, tzinfo=timezone.utc)

def source_for(handler) -> TiingoEODDataSource:
    client = httpx.Client(transport=httpx.MockTransport(handler))
    return TiingoEODDataSource("secret", client=client, clock=lambda: NOW)

def test_parses_and_normalizes_tiingo_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Token secret"
        return httpx.Response(200, json=[{"date": "2025-01-02T00:00:00.000Z", "open": 100, "high": 111, "low": 99, "close": 110, "volume": 1000, "adjOpen": 50, "adjHigh": 55.5, "adjLow": 49.5, "adjClose": 55, "adjVolume": 2000, "divCash": 0.25, "splitFactor": 2}])
    bar = source_for(handler).fetch_daily_bars("aapl", date(2025, 1, 2), date(2025, 1, 2))[0]
    assert bar.ticker == "AAPL"
    assert bar.adjusted_close == 55
    assert bar.split_factor == 2
    assert bar.dividend_cash == 0.25
    assert bar.available_at.hour == 20
    assert bar.available_at.tzinfo is not None

def test_optional_adjusted_fields_can_be_missing() -> None:
    payload = [{"date": "2025-01-02T00:00:00Z", "open": 10, "high": 11, "low": 9, "close": 10, "volume": 0}]
    bars = source_for(lambda _: httpx.Response(200, json=payload)).fetch_daily_bars("AAPL", date(2025, 1, 2), date(2025, 1, 2))
    assert bars[0].adjusted_close is None
    assert bars[0].split_factor == 1

def test_empty_response_is_valid() -> None:
    assert source_for(lambda _: httpx.Response(200, json=[])).fetch_daily_bars("AAPL", date(2025, 1, 1), date(2025, 1, 2)) == []

@pytest.mark.parametrize("status,exception", [(500, DataSourceError), (429, DataSourceRateLimitError)])
def test_http_errors_are_explicit(status, exception) -> None:
    with pytest.raises(exception):
        source_for(lambda _: httpx.Response(status)).fetch_daily_bars("AAPL", date(2025, 1, 1), date(2025, 1, 2))

def test_invalid_ticker_is_rejected_without_http() -> None:
    with pytest.raises(ValueError, match="invalid ticker"):
        source_for(lambda _: pytest.fail("HTTP must not be called")).fetch_daily_bars("bad ticker", date(2025, 1, 1), date(2025, 1, 2))

def test_provider_alias_is_used_only_for_request_and_internal_ticker_is_preserved() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert "/BRK-B/prices" in str(request.url)
        return httpx.Response(200, json=[{
            "date": "2025-01-02T00:00:00Z", "open": 10, "high": 11,
            "low": 9, "close": 10, "volume": 100,
        }])
    source = TiingoEODDataSource(
        "secret", client=httpx.Client(transport=httpx.MockTransport(handler)), clock=lambda: NOW,
        symbol_aliases={"tiingo": {"BRK.B": "BRK-B"}},
    )
    bars = source.fetch_daily_bars("BRK.B", date(2025, 1, 2), date(2025, 1, 2))
    assert bars[0].ticker == "BRK.B"
