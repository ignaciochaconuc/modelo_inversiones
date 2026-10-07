"""Explicit, versioned model feature sets."""
from investment_system.data.schemas.features import FEATURE_COLUMNS

QUANTITATIVE_BASELINE_VERSION = "quantitative-baseline-v1"
QUANTITATIVE_BASELINE_FEATURES = (
    "return_1d", "return_2d", "return_5d", "return_10d", "return_20d", "return_60d",
    "gap_open", "intraday_return", "overnight_return",
    "momentum_5d", "momentum_10d", "momentum_20d", "momentum_60d", "momentum_120d",
    "relative_momentum_spy_5d", "relative_momentum_spy_20d", "relative_momentum_spy_60d",
    "volatility_5d", "volatility_10d", "volatility_20d", "volatility_60d",
    "downside_volatility", "atr_pct", "rsi_14", "macd_pct", "macd_signal_pct",
    "macd_histogram_pct", "distance_ma10", "distance_ma20", "distance_ma50",
    "distance_ma200", "volume_ratio_5d", "volume_ratio_20d", "volume_change_1d",
    "avg_dollar_volume_20d", "avg_dollar_volume_60d", "max_drawdown_20d",
    "max_drawdown_60d", "spy_return_1d", "spy_return_5d", "spy_return_20d",
    "excess_return_5d", "excess_return_20d", "beta_20d", "beta_60d",
    "correlation_spy_20d", "correlation_spy_60d", "distance_52w_high",
    "distance_52w_low", "percentile_price_252d", "percentile_volume_252d",
    "percentile_volatility_252d",
)
LOG1P_FEATURES = ("avg_dollar_volume_20d", "avg_dollar_volume_60d")
FORBIDDEN_BASELINE_FEATURES = (
    "split_adjusted_open", "split_adjusted_high", "split_adjusted_low",
    "split_adjusted_close", "split_adjusted_volume", "atr_14", "macd",
    "macd_signal", "macd_histogram", "sector_return_5d", "sector_return_20d",
    "relative_sector_return_20d",
)

if len(QUANTITATIVE_BASELINE_FEATURES) != len(set(QUANTITATIVE_BASELINE_FEATURES)):
    raise RuntimeError("quantitative baseline feature set contains duplicates")
if not set(QUANTITATIVE_BASELINE_FEATURES) <= set(FEATURE_COLUMNS):
    raise RuntimeError("quantitative baseline feature set contains unregistered columns")
if set(QUANTITATIVE_BASELINE_FEATURES) & set(FORBIDDEN_BASELINE_FEATURES):
    raise RuntimeError("quantitative baseline feature set contains forbidden columns")
