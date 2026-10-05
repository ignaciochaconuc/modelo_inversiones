import numpy as np
import pandas as pd
import pytest
from investment_system.features.builder import FeatureBuilder
from investment_system.features.quantitative import build_quantitative_features, moving_average_distance, rolling_percentile, rolling_volatility

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

def test_historical_position_features_require_full_window() -> None:
    close = pd.Series(np.arange(1.0, 253.0))
    frame = pd.DataFrame({
        "split_adjusted_open": close, "split_adjusted_high": close,
        "split_adjusted_low": close, "split_adjusted_close": close,
        "split_adjusted_volume": np.arange(252.0),
    })
    result = build_quantitative_features(frame)
    assert pd.isna(result["distance_52w_high"].iloc[250])
    assert result["distance_52w_high"].iloc[251] == 0
    assert result["distance_52w_low"].iloc[251] == pytest.approx(252 / 1 - 1)
    assert result["percentile_price_252d"].iloc[251] == 1
    assert result["percentile_volume_252d"].iloc[251] == 1

def test_rolling_percentile_uses_average_rank_for_ties() -> None:
    result = rolling_percentile(pd.Series([1.0, 2.0, 2.0, 3.0]), window=4)
    assert result.iloc[-1] == 1
    tied = rolling_percentile(pd.Series([1.0, 2.0, 2.0, 2.0]), window=4)
    assert tied.iloc[-1] == pytest.approx(2 / 3)

def test_benchmark_features_are_computed_from_explicit_series() -> None:
    asset = pd.Series(100 * (1 + pd.Series(np.linspace(0.001, 0.02, 80))).cumprod())
    spy = pd.Series(100 * (1 + pd.Series(np.linspace(0.002, 0.01, 80))).cumprod())
    frame = pd.DataFrame({
        "split_adjusted_open": asset, "split_adjusted_high": asset,
        "split_adjusted_low": asset, "split_adjusted_close": asset,
        "split_adjusted_volume": 1000.0,
    })
    result = build_quantitative_features(frame, spy)
    assert result["spy_return_5d"].iloc[-1] == pytest.approx(spy.iloc[-1] / spy.iloc[-6] - 1)
    assert result["excess_return_5d"].iloc[-1] == pytest.approx(result["return_5d"].iloc[-1] - result["spy_return_5d"].iloc[-1])
    assert result["correlation_spy_20d"].iloc[-1] > 0.99
