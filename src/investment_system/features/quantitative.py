import numpy as np
import pandas as pd

TRADING_DAYS = 252

def returns(prices: pd.Series, periods: int) -> pd.Series:
    return prices.pct_change(periods, fill_method=None)

def momentum(prices: pd.Series, periods: int) -> pd.Series:
    return returns(prices, periods)

def rolling_volatility(prices: pd.Series, window: int, annualize: bool = True) -> pd.Series:
    scale = np.sqrt(TRADING_DAYS) if annualize else 1.0
    return prices.pct_change(fill_method=None).rolling(window).std(ddof=1) * scale

def downside_volatility(prices: pd.Series, window: int = 20, annualize: bool = True) -> pd.Series:
    changes = prices.pct_change(fill_method=None)
    downside = changes.where(changes < 0, 0.0)
    scale = np.sqrt(TRADING_DAYS) if annualize else 1.0
    return downside.rolling(window).apply(lambda x: np.sqrt(np.mean(np.square(x))), raw=True) * scale

def rsi(prices: pd.Series, window: int = 14) -> pd.Series:
    delta = prices.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False, min_periods=window).mean()
    rs = gain / loss.replace(0, np.nan)
    result = 100 - 100 / (1 + rs)
    return result.where(loss != 0, 100.0)

def moving_average_distance(prices: pd.Series, window: int) -> pd.Series:
    average = prices.rolling(window).mean()
    return (prices - average) / average

def volume_ratio(volume: pd.Series, window: int) -> pd.Series:
    return volume / volume.rolling(window).mean()

def average_true_range(frame: pd.DataFrame, window: int = 14) -> pd.Series:
    previous_close = frame["close"].shift(1)
    true_range = pd.concat([
        frame["high"] - frame["low"],
        (frame["high"] - previous_close).abs(),
        (frame["low"] - previous_close).abs(),
    ], axis=1).max(axis=1)
    return true_range.rolling(window).mean()

def rolling_max_drawdown(prices: pd.Series, window: int) -> pd.Series:
    return prices.rolling(window).apply(lambda x: np.min(x / np.maximum.accumulate(x) - 1), raw=True)

def rolling_correlation(prices: pd.Series, benchmark: pd.Series, window: int) -> pd.Series:
    return prices.pct_change(fill_method=None).rolling(window).corr(benchmark.pct_change(fill_method=None))

def rolling_beta(prices: pd.Series, benchmark: pd.Series, window: int) -> pd.Series:
    asset_returns = prices.pct_change(fill_method=None)
    benchmark_returns = benchmark.pct_change(fill_method=None)
    return asset_returns.rolling(window).cov(benchmark_returns) / benchmark_returns.rolling(window).var()

def build_quantitative_features(frame: pd.DataFrame, benchmark_close: pd.Series | None = None) -> pd.DataFrame:
    """Return a copy enriched with causal OHLCV features."""
    required = {"open", "high", "low", "close", "adjusted_close", "volume"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"missing OHLCV columns: {sorted(missing)}")
    result = frame.copy().sort_index()
    price = result["adjusted_close"]
    for period in (1, 2, 5, 10, 20, 60):
        result[f"return_{period}d"] = returns(price, period)
    for period in (5, 10, 20, 60, 120):
        result[f"momentum_{period}d"] = momentum(price, period)
    for window in (5, 10, 20, 60):
        result[f"volatility_{window}d"] = rolling_volatility(price, window)
    result["downside_volatility"] = downside_volatility(price)
    result["gap_open"] = result["open"] / result["close"].shift(1) - 1
    result["intraday_return"] = result["close"] / result["open"] - 1
    result["overnight_return"] = result["open"] / result["close"].shift(1) - 1
    result["rsi_14"] = rsi(price)
    result["atr_14"] = average_true_range(result)
    for window in (10, 20, 50, 200):
        result[f"distance_ma{window}"] = moving_average_distance(price, window)
    for window in (5, 20):
        result[f"volume_ratio_{window}d"] = volume_ratio(result["volume"], window)
    result["volume_change_1d"] = result["volume"].pct_change(fill_method=None)
    for window in (20, 60):
        result[f"avg_dollar_volume_{window}d"] = (price * result["volume"]).rolling(window).mean()
        result[f"max_drawdown_{window}d"] = rolling_max_drawdown(price, window)
    ema12, ema26 = price.ewm(span=12, adjust=False).mean(), price.ewm(span=26, adjust=False).mean()
    result["macd"] = ema12 - ema26
    result["macd_signal"] = result["macd"].ewm(span=9, adjust=False).mean()
    result["macd_histogram"] = result["macd"] - result["macd_signal"]
    if benchmark_close is not None:
        benchmark = benchmark_close.reindex(result.index)
        for period in (5, 20, 60):
            result[f"relative_momentum_spy_{period}d"] = returns(price, period) - returns(benchmark, period)
        for window in (20, 60):
            result[f"correlation_spy_{window}d"] = rolling_correlation(price, benchmark, window)
            result[f"beta_{window}d"] = rolling_beta(price, benchmark, window)
    return result
