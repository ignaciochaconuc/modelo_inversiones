import pandas as pd
from investment_system.features.quantitative import build_quantitative_features

class FeatureBuilder:
    def build(self, ohlcv: pd.DataFrame, benchmark_close: pd.Series | None = None) -> pd.DataFrame:
        return build_quantitative_features(ohlcv, benchmark_close)

    def add_targets(self, frame: pd.DataFrame, price_column: str = "adjusted_close") -> pd.DataFrame:
        result = frame.copy()
        for horizon in (5, 10, 20):
            result[f"target_return_{horizon}d"] = result[price_column].shift(-horizon) / result[price_column] - 1
        result["target_positive_10d"] = (result["target_return_10d"] > 0).astype("Int64")
        result.loc[result["target_return_10d"].isna(), "target_positive_10d"] = pd.NA
        return result
