class InvestmentSystemError(Exception):
    """Base domain exception."""

class PointInTimeViolation(InvestmentSystemError):
    """Information was unavailable at decision time."""

class ConfigurationError(InvestmentSystemError):
    """Missing or invalid configuration."""

class ExternalCallDisabled(InvestmentSystemError):
    """Provider calls are disabled in phase zero."""
