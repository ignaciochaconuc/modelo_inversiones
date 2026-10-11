"""External source contracts and adapters."""
from investment_system.data.sources.tiingo import TiingoEODDataSource
from investment_system.data.sources.finnhub_news import FinnhubNewsProvider
from investment_system.data.sources.news import NewsFetchRequest, NewsIngestionPolicy, NewsProvider

__all__ = [
    "TiingoEODDataSource", "FinnhubNewsProvider", "NewsFetchRequest",
    "NewsIngestionPolicy", "NewsProvider",
]
