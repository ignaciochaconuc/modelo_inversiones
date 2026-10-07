"""Pure NAV and return metrics for deterministic historical reports."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
import math

import numpy as np
import pandas as pd

from investment_system.backtesting.schemas import PerformanceMetrics, PortfolioSnapshot


TRADING_PERIODS_PER_YEAR = 252
CALENDAR_DAYS_PER_YEAR = 365.25


@dataclass(frozen=True)
class DrawdownStatistics:
    """Maximum drawdown and its peak, trough, and optional recovery dates."""

    maximum_drawdown: float
    peak_date: date
    trough_date: date
    recovery_date: date | None


def _finite_series(values: pd.Series, *, name: str, allow_empty: bool = False) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    if numeric.empty and not allow_empty:
        raise ValueError(f"{name} must not be empty")
    if numeric.isna().any() or not np.isfinite(numeric.to_numpy()).all():
        raise ValueError(f"{name} must contain only finite values; NaN is not allowed")
    return numeric


def _ordered_nav(nav: pd.Series) -> pd.Series:
    numeric = _finite_series(nav, name="NAV")
    if not isinstance(numeric.index, pd.DatetimeIndex):
        raise ValueError("NAV must use a DatetimeIndex")
    if not numeric.index.is_monotonic_increasing or numeric.index.has_duplicates:
        raise ValueError("NAV timestamps must be unique and strictly increasing")
    if (numeric <= 0).any():
        raise ValueError("NAV must remain positive")
    return numeric


def nav_series_from_snapshots(snapshots: list[PortfolioSnapshot]) -> pd.Series:
    """Build the ordered NAV source of truth from final session snapshots."""
    if not snapshots:
        raise ValueError("at least one portfolio snapshot is required")
    series = pd.Series(
        [snapshot.nav for snapshot in snapshots],
        index=pd.DatetimeIndex([snapshot.as_of for snapshot in snapshots]),
        dtype=float,
        name="nav",
    )
    return _ordered_nav(series)


def daily_returns(nav: pd.Series) -> pd.Series:
    """Return NAV_t / NAV_(t-1) - 1; the first snapshot has no return."""
    ordered = _ordered_nav(nav)
    result = ordered.pct_change(fill_method=None).iloc[1:]
    result.name = "daily_return"
    return result


def cumulative_return(returns: pd.Series) -> float:
    """Compound a finite return series; an empty series represents zero return."""
    clean = _finite_series(returns, name="returns", allow_empty=True)
    return float((1 + clean).prod() - 1)


def cumulative_return_from_nav(nav: pd.Series) -> float:
    ordered = _ordered_nav(nav)
    return float(ordered.iloc[-1] / ordered.iloc[0] - 1)


def cagr(nav: pd.Series) -> float | None:
    """Annualize by actual calendar days using 365.25; one date returns None."""
    ordered = _ordered_nav(nav)
    calendar_days = (ordered.index[-1].date() - ordered.index[0].date()).days
    if calendar_days <= 0:
        return None
    return float(
        (ordered.iloc[-1] / ordered.iloc[0])
        ** (CALENDAR_DAYS_PER_YEAR / calendar_days)
        - 1
    )


def annualized_volatility(
    returns: pd.Series, periods: int = TRADING_PERIODS_PER_YEAR,
) -> float | None:
    """Sample standard deviation (ddof=1) annualized by sqrt(periods)."""
    clean = _finite_series(returns, name="returns", allow_empty=True)
    if len(clean) < 2:
        return None
    return float(clean.std(ddof=1) * math.sqrt(periods))


def sharpe_ratio(
    returns: pd.Series, periods: int = TRADING_PERIODS_PER_YEAR,
) -> float | None:
    """Arithmetic Sharpe with Phase 2A.3 risk-free rate fixed at zero."""
    clean = _finite_series(returns, name="returns", allow_empty=True)
    if len(clean) < 2:
        return None
    volatility = float(clean.std(ddof=1))
    if math.isclose(volatility, 0.0, abs_tol=1e-15):
        return None
    return float(clean.mean() / volatility * math.sqrt(periods))


def sortino_ratio(
    returns: pd.Series, periods: int = TRADING_PERIODS_PER_YEAR,
) -> float | None:
    """Annual mean divided by annualized RMS downside; MAR is fixed at zero."""
    clean = _finite_series(returns, name="returns", allow_empty=True)
    if len(clean) < 2:
        return None
    downside = np.minimum(clean.to_numpy(), 0.0)
    daily_downside_deviation = float(np.sqrt(np.mean(np.square(downside))))
    if math.isclose(daily_downside_deviation, 0.0, abs_tol=1e-15):
        return None
    return float(clean.mean() * periods / (daily_downside_deviation * math.sqrt(periods)))


def drawdown_statistics(nav: pd.Series) -> DrawdownStatistics:
    """Return negative-or-zero maximum drawdown with its dated lifecycle."""
    ordered = _ordered_nav(nav)
    running_max = ordered.cummax()
    drawdowns = ordered / running_max - 1
    trough_timestamp = drawdowns.idxmin()
    trough_position = ordered.index.get_loc(trough_timestamp)
    through_trough = ordered.iloc[: trough_position + 1]
    peak_timestamp = through_trough.idxmax()
    peak_nav = float(ordered.loc[peak_timestamp])
    after_trough = ordered.iloc[trough_position + 1 :]
    recovered = after_trough[after_trough >= peak_nav]
    recovery_date = None if recovered.empty else recovered.index[0].date()
    return DrawdownStatistics(
        maximum_drawdown=float(drawdowns.loc[trough_timestamp]),
        peak_date=peak_timestamp.date(),
        trough_date=trough_timestamp.date(),
        recovery_date=recovery_date,
    )


def max_drawdown(nav: pd.Series) -> float:
    """Maximum drawdown as a non-positive return, for example -0.23."""
    return drawdown_statistics(nav).maximum_drawdown


def performance_metrics(nav: pd.Series) -> PerformanceMetrics:
    """Calculate the complete version-1 performance block from NAV only."""
    ordered = _ordered_nav(nav)
    returns = daily_returns(ordered)
    drawdown = drawdown_statistics(ordered)
    return PerformanceMetrics(
        start_date=ordered.index[0].date(),
        end_date=ordered.index[-1].date(),
        initial_nav=float(ordered.iloc[0]),
        final_nav=float(ordered.iloc[-1]),
        session_count=len(ordered),
        return_observation_count=len(returns),
        cumulative_return=cumulative_return_from_nav(ordered),
        cagr=cagr(ordered),
        annualized_volatility=annualized_volatility(returns),
        sharpe_ratio=sharpe_ratio(returns),
        sortino_ratio=sortino_ratio(returns),
        max_drawdown=drawdown.maximum_drawdown,
        drawdown_peak_date=drawdown.peak_date,
        drawdown_trough_date=drawdown.trough_date,
        drawdown_recovery_date=drawdown.recovery_date,
    )
