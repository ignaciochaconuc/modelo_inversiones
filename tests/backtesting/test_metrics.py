import math

import numpy as np
import pandas as pd
import pytest

from investment_system.backtesting.metrics import (
    annualized_volatility, cagr, cumulative_return, cumulative_return_from_nav,
    daily_returns, drawdown_statistics, max_drawdown, performance_metrics,
    sharpe_ratio, sortino_ratio,
)


def nav(*values: float, dates: list[str] | None = None) -> pd.Series:
    index = pd.to_datetime(
        dates or [f"2025-01-{day:02d}T21:15:00Z" for day in range(1, len(values) + 1)],
        utc=True,
    )
    return pd.Series(values, index=index, dtype=float)


def test_constant_nav_has_zero_return_volatility_and_drawdown() -> None:
    values = nav(100, 100, 100)
    returns = daily_returns(values)
    assert returns.tolist() == [0, 0]
    assert cumulative_return_from_nav(values) == 0
    assert cumulative_return(returns) == 0
    assert annualized_volatility(returns) == 0
    assert sharpe_ratio(returns) is None
    assert sortino_ratio(returns) is None
    assert max_drawdown(values) == 0


def test_monotonic_nav_has_zero_maximum_drawdown() -> None:
    assert max_drawdown(nav(100, 110, 120, 130)) == 0


def test_known_drawdown_reports_exact_peak_trough_and_recovery() -> None:
    values = nav(100, 120, 90, 110, 121)
    result = drawdown_statistics(values)
    assert result.maximum_drawdown == pytest.approx(-0.25)
    assert result.peak_date.isoformat() == "2025-01-02"
    assert result.trough_date.isoformat() == "2025-01-03"
    assert result.recovery_date.isoformat() == "2025-01-05"


def test_cumulative_return_uses_first_and_final_nav() -> None:
    values = nav(100, 90, 125)
    assert cumulative_return_from_nav(values) == pytest.approx(0.25)
    assert cumulative_return(daily_returns(values)) == pytest.approx(0.25)


def test_cagr_uses_actual_calendar_days_and_365_25() -> None:
    values = nav(100, 110, dates=["2024-01-01T21:15:00Z", "2024-12-31T21:15:00Z"])
    assert cagr(values) == pytest.approx(1.1 ** (365.25 / 365) - 1)


def test_volatility_sharpe_and_sortino_follow_documented_formulas() -> None:
    returns = pd.Series([0.01, -0.02, 0.03], dtype=float)
    expected_volatility = float(returns.std(ddof=1) * math.sqrt(252))
    expected_sharpe = float(returns.mean() / returns.std(ddof=1) * math.sqrt(252))
    downside = np.minimum(returns.to_numpy(), 0)
    downside_deviation = float(np.sqrt(np.mean(np.square(downside))) * math.sqrt(252))
    expected_sortino = float(returns.mean() * 252 / downside_deviation)
    assert annualized_volatility(returns) == pytest.approx(expected_volatility)
    assert sharpe_ratio(returns) == pytest.approx(expected_sharpe)
    assert sortino_ratio(returns) == pytest.approx(expected_sortino)


def test_insufficient_observations_are_explicitly_none() -> None:
    result = performance_metrics(nav(100))
    assert result.cagr is None
    assert result.annualized_volatility is None
    assert result.sharpe_ratio is None
    assert result.sortino_ratio is None
    assert result.return_observation_count == 0


def test_zero_volatility_never_produces_infinity() -> None:
    returns = pd.Series([0.01, 0.01, 0.01], dtype=float)
    assert annualized_volatility(returns) == 0
    assert sharpe_ratio(returns) is None
    assert sortino_ratio(returns) is None


@pytest.mark.parametrize(
    "function, values",
    [
        (cumulative_return, pd.Series([0.1, float("nan")])),
        (annualized_volatility, pd.Series([0.1, float("nan")])),
        (sharpe_ratio, pd.Series([0.1, float("inf")])),
        (sortino_ratio, pd.Series([0.1, float("nan")])),
    ],
)
def test_return_metrics_reject_nan_and_infinity(function, values) -> None:
    with pytest.raises(ValueError, match="finite values"):
        function(values)


def test_nav_rejects_nan_nonpositive_and_unordered_timestamps() -> None:
    with pytest.raises(ValueError, match="finite values"):
        daily_returns(nav(100, float("nan")))
    with pytest.raises(ValueError, match="positive"):
        daily_returns(nav(100, 0))
    unordered = pd.Series(
        [100, 101],
        index=pd.to_datetime(["2025-01-02T21:15:00Z", "2025-01-01T21:15:00Z"]),
    )
    with pytest.raises(ValueError, match="strictly increasing"):
        daily_returns(unordered)
