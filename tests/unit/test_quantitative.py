import numpy as np
import pandas as pd
import pytest
from investment_system.features.builder import FeatureBuilder
from investment_system.features.quantitative import moving_average_distance, rolling_volatility

def test_target_return_10d() -> None:
    prices = pd.DataFrame({"split_adjusted_close": np.arange(100.0, 121.0)})
    result = FeatureBuilder().add_targets(prices)
    assert result.loc[0, "target_return_10d"] == pytest.approx(110 / 100 - 1)

def test_moving_average_distance_is_relative() -> None:
    values = pd.Series([10.0, 20.0, 30.0])
    assert moving_average_distance(values, 2).iloc[-1] == pytest.approx((30 - 25) / 25)

def test_rolling_volatility_constant_returns() -> None:
    prices = pd.Series(100 * 1.01 ** np.arange(10))
    assert rolling_volatility(prices, 5).iloc[-1] == pytest.approx(0.0, abs=1e-12)

def test_builder_uses_internal_split_adjusted_ohlcv_for_absolute_features() -> None:
    close = pd.Series(np.linspace(100, 119, 20))
    frame = pd.DataFrame({
        "split_adjusted_open": close,
        "split_adjusted_high": close + 1,
        "split_adjusted_low": close - 1,
        "split_adjusted_close": close,
        "split_adjusted_volume": 1000.0,
        "open": close * 10,
        "high": (close + 1) * 10,
        "low": (close - 1) * 10,
        "close": close * 10,
        "volume": 10.0,
    })
    result = FeatureBuilder().build(frame)
    assert result["atr_14"].iloc[-1] == pytest.approx(2.0)
    assert result["atr_pct"].iloc[-1] == pytest.approx(2 / 119)
    assert result["close"].iloc[-1] == 119
    assert result["macd_pct"].iloc[-1] == pytest.approx(result["macd"].iloc[-1] / 119)
