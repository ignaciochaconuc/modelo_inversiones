"""Provider-neutral corporate-action normalization."""
from collections.abc import Iterable

import pandas as pd

from investment_system.data.schemas.market import CorporateAction, CorporateActionType, MarketBar

NORMALIZATION_VERSION = "split-adjusted-v1"

def extract_corporate_actions(bars: Iterable[MarketBar], currency: str = "USD") -> list[CorporateAction]:
    """Extract and deduplicate actions embedded in EOD bars."""
    unique: dict[tuple[str, object, str, str], CorporateAction] = {}
    for bar in bars:
        common = dict(
            ticker=bar.ticker, effective_date=bar.trading_date, provider=bar.provider,
            schema_version=bar.schema_version, currency=currency, observed_at=bar.observed_at,
            published_at=bar.published_at, available_at=bar.available_at, ingested_at=bar.ingested_at,
        )
        if bar.split_factor != 1.0:
            action = CorporateAction(action_type=CorporateActionType.SPLIT, split_factor=bar.split_factor, **common)
            unique[(bar.ticker, bar.trading_date, action.action_type.value, bar.provider)] = action
        if bar.dividend_cash > 0:
            action = CorporateAction(action_type=CorporateActionType.DIVIDEND, dividend_cash=bar.dividend_cash, **common)
            unique[(bar.ticker, bar.trading_date, action.action_type.value, bar.provider)] = action
    return list(unique.values())

def build_split_adjusted_series(
    raw_bars: pd.DataFrame,
    actions: pd.DataFrame,
    normalization_version: str = NORMALIZATION_VERSION,
) -> pd.DataFrame:
    """Adjust historical OHLCV to the latest share basis using future splits only.

    Internal convention: split_factor is new shares per old share. A 2:1 split is
    2.0 and a 1:2 reverse split is 0.5. The effective date contains post-split
    prices, so an action affects rows strictly before that date. Dividends are
    deliberately ignored.
    """
    if raw_bars.empty:
        return raw_bars.copy()
    bars = raw_bars.copy()
    bars["trading_date"] = pd.to_datetime(bars["trading_date"]).dt.date
    bars = bars.sort_values(["ticker", "trading_date"]).reset_index(drop=True)
    split_actions = actions.copy()
    if not split_actions.empty:
        split_actions["effective_date"] = pd.to_datetime(split_actions["effective_date"]).dt.date
        split_actions = split_actions[split_actions["action_type"].astype(str).str.lower().str.endswith("split")]

    factors: list[float] = []
    for row in bars.itertuples(index=False):
        if split_actions.empty:
            factor = 1.0
        else:
            relevant = split_actions[
                (split_actions["ticker"] == row.ticker)
                & (split_actions["effective_date"] > row.trading_date)
            ]
            factor = float(relevant["split_factor"].fillna(1.0).prod())
        factors.append(factor)
    bars["cumulative_future_split_factor"] = factors
    for column in ("open", "high", "low", "close"):
        bars[f"split_adjusted_{column}"] = bars[column] / bars["cumulative_future_split_factor"]
    bars["split_adjusted_volume"] = bars["volume"] * bars["cumulative_future_split_factor"]
    bars["normalization_version"] = normalization_version
    keep = [
        "ticker", "trading_date", "provider", "schema_version", "ingested_at",
        "cumulative_future_split_factor", "split_adjusted_open", "split_adjusted_high",
        "split_adjusted_low", "split_adjusted_close", "split_adjusted_volume", "normalization_version",
    ]
    return bars[keep]
