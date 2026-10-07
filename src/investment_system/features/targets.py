"""Supervised labels. This module is never used by live feature generation."""
import pandas as pd

from investment_system.data.calendar import TradingCalendar
from investment_system.data.normalization import build_latest_basis_split_adjusted_series

SUPPORTED_HORIZONS = (5, 10, 20)
DEFAULT_HORIZON = 10
TARGET_SCHEMA_VERSION = "corporate-action-safe-target-v3"
TARGET_COLUMNS = tuple(
    [f"target_return_{horizon}d" for horizon in SUPPORTED_HORIZONS]
    + [f"target_positive_{horizon}d" for horizon in SUPPORTED_HORIZONS]
    + [f"target_rank_{horizon}d" for horizon in SUPPORTED_HORIZONS]
)
TARGET_METADATA_COLUMNS = (
    *(f"target_end_date_{horizon}d" for horizon in SUPPORTED_HORIZONS),
    *(f"target_corporate_action_contaminated_{horizon}d" for horizon in SUPPORTED_HORIZONS),
    *(f"target_{horizon}d_training_eligible" for horizon in SUPPORTED_HORIZONS),
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
        return pd.DataFrame(columns=["ticker", "decision_date", *TARGET_COLUMNS, *TARGET_METADATA_COLUMNS])
    adjusted = adjusted.sort_values("trading_date")
    price_by_date = adjusted.set_index("trading_date")["split_adjusted_close"]
    result = adjusted[["ticker", "trading_date"]].rename(columns={"trading_date": "decision_date"}).copy()
    for horizon in SUPPORTED_HORIZONS:
        future_dates = result["decision_date"].map(lambda value: _future_session(calendar, value, horizon))
        result[f"target_end_date_{horizon}d"] = future_dates
        future_prices = future_dates.map(price_by_date)
        current_prices = result["decision_date"].map(price_by_date)
        result[f"target_return_{horizon}d"] = future_prices.to_numpy() / current_prices.to_numpy() - 1
        positive = (result[f"target_return_{horizon}d"] > 0).astype("Int64")
        result[f"target_positive_{horizon}d"] = positive.mask(
            result[f"target_return_{horizon}d"].isna(), pd.NA
        )
    excluded_dates: set[object] = set()
    if contamination_events is not None and not contamination_events.empty:
        eligible_events = contamination_events[contamination_events["training_exclusion"].fillna(False)]
        excluded_dates = set(pd.to_datetime(eligible_events["event_date"]).dt.date)
    for horizon in SUPPORTED_HORIZONS:
        future_dates = result[f"target_end_date_{horizon}d"]
        contaminated = [any(origin < event <= future for event in excluded_dates)
                        for origin, future in zip(result["decision_date"], future_dates)]
        result[f"target_corporate_action_contaminated_{horizon}d"] = contaminated
        result[f"target_{horizon}d_training_eligible"] = (
            result[f"target_return_{horizon}d"].notna() & ~pd.Series(contaminated, index=result.index)
        )
    return result

def add_cross_sectional_rank(targets: pd.DataFrame, minimum_assets: int = 20) -> pd.DataFrame:
    """Rank every supported return to [0, 1], using only eligible labels."""
    result = targets.copy()
    for horizon in SUPPORTED_HORIZONS:
        rank_column = f"target_rank_{horizon}d"
        return_column = f"target_return_{horizon}d"
        eligibility_column = f"target_{horizon}d_training_eligible"
        result[rank_column] = float("nan")
        if return_column not in result:
            continue
        for _, indices in result.groupby("decision_date").groups.items():
            values = result.loc[indices, return_column]
            if eligibility_column in result:
                values = values[result.loc[indices, eligibility_column].fillna(False)]
            values = values.dropna()
            if len(values) < minimum_assets:
                continue
            ranks = values.rank(method="average", ascending=True)
            result.loc[values.index, rank_column] = (ranks - 1) / (len(values) - 1)
    return result


def build_training_dataset(features: pd.DataFrame, targets: pd.DataFrame, horizon: int = 10) -> pd.DataFrame:
    """Explicit supervised join with eligibility kept outside inference features."""
    if horizon not in SUPPORTED_HORIZONS:
        raise ValueError("horizon must be 5, 10, or 20")
    joined = features.merge(targets, on=["ticker", "decision_date"], how="inner", validate="one_to_one")
    target_flag = f"target_{horizon}d_training_eligible"
    joined["training_eligible"] = (
        joined["model_eligible"].fillna(False)
        & ~joined["feature_corporate_action_contaminated"].fillna(False)
        & joined[target_flag].fillna(False)
    )
    return joined
