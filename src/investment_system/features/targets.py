"""Supervised labels. This module is never used by live feature generation."""
import pandas as pd

from investment_system.data.calendar import TradingCalendar
from investment_system.data.normalization import build_latest_basis_split_adjusted_series

TARGET_COLUMNS = ("target_return_5d", "target_return_10d", "target_return_20d", "target_positive_10d", "target_rank_10d")
TARGET_METADATA_COLUMNS = (
    "target_corporate_action_contaminated_5d", "target_corporate_action_contaminated_10d",
    "target_corporate_action_contaminated_20d", "target_5d_training_eligible",
    "target_10d_training_eligible", "target_20d_training_eligible",
)

def _future_session(calendar: TradingCalendar, origin: object, horizon: int) -> object:
    session = pd.Timestamp(origin).date()
    for _ in range(horizon):
        session = calendar.next_session(session)
    return session

def build_price_targets(
    raw_bars: pd.DataFrame,
    actions: pd.DataFrame,
    calendar: TradingCalendar,
    contamination_events: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Build split-consistent future price returns, excluding dividends.

    Future corporate actions are allowed here only because this is target
    construction, never feature construction.
    """
    adjusted = build_latest_basis_split_adjusted_series(raw_bars, actions)
    if adjusted.empty:
        return pd.DataFrame(columns=["ticker", "decision_date", *TARGET_COLUMNS[:-1]])
    adjusted = adjusted.sort_values("trading_date")
    price_by_date = adjusted.set_index("trading_date")["split_adjusted_close"]
    result = adjusted[["ticker", "trading_date"]].rename(columns={"trading_date": "decision_date"}).copy()
    for horizon in (5, 10, 20):
        future_dates = result["decision_date"].map(lambda value: _future_session(calendar, value, horizon))
        future_prices = future_dates.map(price_by_date)
        current_prices = result["decision_date"].map(price_by_date)
        result[f"target_return_{horizon}d"] = future_prices.to_numpy() / current_prices.to_numpy() - 1
    result["target_positive_10d"] = (result["target_return_10d"] > 0).astype("Int64")
    result.loc[result["target_return_10d"].isna(), "target_positive_10d"] = pd.NA
    excluded_dates: set[object] = set()
    if contamination_events is not None and not contamination_events.empty:
        eligible_events = contamination_events[contamination_events["training_exclusion"].fillna(False)]
        excluded_dates = set(pd.to_datetime(eligible_events["event_date"]).dt.date)
    for horizon in (5, 10, 20):
        future_dates = result["decision_date"].map(lambda value: _future_session(calendar, value, horizon))
        contaminated = [any(origin < event <= future for event in excluded_dates)
                        for origin, future in zip(result["decision_date"], future_dates)]
        result[f"target_corporate_action_contaminated_{horizon}d"] = contaminated
        result[f"target_{horizon}d_training_eligible"] = (
            result[f"target_return_{horizon}d"].notna() & ~pd.Series(contaminated, index=result.index)
        )
    return result

def add_cross_sectional_rank(targets: pd.DataFrame, minimum_assets: int = 20) -> pd.DataFrame:
    """Rank 10-day returns to [0, 1], with average rank for ties."""
    result = targets.copy()
    result["target_rank_10d"] = float("nan")
    for _, indices in result.groupby("decision_date").groups.items():
        values = result.loc[indices, "target_return_10d"]
        if "target_10d_training_eligible" in result:
            values = values[result.loc[indices, "target_10d_training_eligible"].fillna(False)]
        values = values.dropna()
        if len(values) < minimum_assets:
            continue
        ranks = values.rank(method="average", ascending=True)
        result.loc[values.index, "target_rank_10d"] = (ranks - 1) / (len(values) - 1)
    return result


def build_training_dataset(features: pd.DataFrame, targets: pd.DataFrame, horizon: int = 10) -> pd.DataFrame:
    """Explicit supervised join with eligibility kept outside inference features."""
    if horizon not in (5, 10, 20):
        raise ValueError("horizon must be 5, 10, or 20")
    joined = features.merge(targets, on=["ticker", "decision_date"], how="inner", validate="one_to_one")
    target_flag = f"target_{horizon}d_training_eligible"
    joined["training_eligible"] = (
        joined["model_eligible"].fillna(False)
        & ~joined["feature_corporate_action_contaminated"].fillna(False)
        & joined[target_flag].fillna(False)
    )
    return joined
