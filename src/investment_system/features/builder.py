import pandas as pd
from investment_system.features.quantitative import OHLCVColumns, SPLIT_ADJUSTED_COLUMNS, build_quantitative_features

class FeatureBuilder:
    def build(self, ohlcv: pd.DataFrame, benchmark_close: pd.Series | None = None, *, columns: OHLCVColumns = SPLIT_ADJUSTED_COLUMNS) -> pd.DataFrame:
        return build_quantitative_features(ohlcv, benchmark_close, columns=columns)
