class InvestmentSystemError(Exception):
    """Base domain exception."""

class PointInTimeViolation(InvestmentSystemError):
    """Information was unavailable at decision time."""

class ConfigurationError(InvestmentSystemError):
    """Missing or invalid configuration."""

class ExternalCallDisabled(InvestmentSystemError):
    """Provider calls are disabled in phase zero."""

class DataSourceError(InvestmentSystemError):
    """A market-data provider request or payload failed."""

class DataSourceRateLimitError(DataSourceError):
    """A provider rejected a request due to rate limiting."""

class DataQualityError(InvestmentSystemError):
    """Market data violates an internal quality invariant."""
