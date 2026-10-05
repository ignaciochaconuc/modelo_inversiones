"""Supervised labels. This module is never used by live feature generation."""
import pandas as pd

from investment_system.data.normalization import build_latest_basis_split_adjusted_series

TARGET_COLUMNS = ("target_return_5d", "target_return_10d", "target_return_20d", "target_positive_10d", "target_rank_10d")

def build_price_targets(raw_bars: pd.DataFrame, actions: pd.DataFrame) -> pd.DataFrame:
    """Build split-consistent future price returns, excluding dividends.

    Future corporate actions are allowed here only because this is target
    construction, never feature construction.
    """
    adjusted = build_latest_basis_split_adjusted_series(raw_bars, actions)
    if adjusted.empty:
        return pd.DataFrame(columns=["ticker", "decision_date", *TARGET_COLUMNS[:-1]])
    adjusted = adjusted.sort_values("trading_date")
    price = adjusted["split_adjusted_close"]
    result = adjusted[["ticker", "trading_date"]].rename(columns={"trading_date": "decision_date"}).copy()
    for horizon in (5, 10, 20):
        result[f"target_return_{horizon}d"] = price.shift(-horizon) / price - 1
    result["target_positive_10d"] = (result["target_return_10d"] > 0).astype("Int64")
    result.loc[result["target_return_10d"].isna(), "target_positive_10d"] = pd.NA
    return result

def add_cross_sectional_rank(targets: pd.DataFrame, minimum_assets: int = 20) -> pd.DataFrame:
    """Rank 10-day returns to [0, 1], with average rank for ties."""
    result = targets.copy()
    result["target_rank_10d"] = float("nan")
    for _, indices in result.groupby("decision_date").groups.items():
        values = result.loc[indices, "target_return_10d"].dropna()
        if len(values) < minimum_assets:
            continue
        ranks = values.rank(method="average", ascending=True)
        result.loc[values.index, "target_rank_10d"] = (ranks - 1) / (len(values) - 1)
    return result
