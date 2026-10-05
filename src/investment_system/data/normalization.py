"""Provider-neutral corporate-action normalization."""
from collections.abc import Iterable
from datetime import date, datetime

import numpy as np
import pandas as pd

from investment_system.data.schemas.market import CorporateAction, CorporateActionType, MarketBar

LATEST_BASIS_VERSION = "split-adjusted-latest-v1"
AS_OF_VERSION = "split-adjusted-as-of-v1"

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

def _split_actions(actions: pd.DataFrame) -> pd.DataFrame:
    if actions.empty:
        return actions.copy()
    result = actions.copy()
    result["effective_date"] = pd.to_datetime(result["effective_date"]).dt.date
    return result[result["action_type"].astype(str).str.lower().str.endswith("split")]

def _apply_splits(raw_bars: pd.DataFrame, split_actions: pd.DataFrame, normalization_version: str, basis: str, as_of: datetime | None = None) -> pd.DataFrame:
    if raw_bars.empty:
        return raw_bars.copy()
    bars = raw_bars.copy()
    bars["trading_date"] = pd.to_datetime(bars["trading_date"]).dt.date
    bars = bars.sort_values(["ticker", "trading_date"]).reset_index(drop=True)
    factors = np.ones(len(bars), dtype=float)
    if not split_actions.empty:
        actions = split_actions.copy()
        actions["effective_date"] = pd.to_datetime(actions["effective_date"]).dt.date
        for ticker, indices in bars.groupby("ticker", sort=False).groups.items():
            ticker_actions = actions[actions["ticker"] == ticker]
            if ticker_actions.empty:
                continue
            daily_factors = ticker_actions.groupby("effective_date", sort=True)["split_factor"].prod()
            split_dates = np.asarray(list(daily_factors.index), dtype="datetime64[D]")
            split_factors = daily_factors.to_numpy(dtype=float, na_value=1.0)
            suffix_products = np.ones(len(split_factors) + 1, dtype=float)
            suffix_products[:-1] = np.cumprod(split_factors[::-1])[::-1]
            bar_dates = np.asarray(bars.loc[indices, "trading_date"].tolist(), dtype="datetime64[D]")
            first_future_split = np.searchsorted(split_dates, bar_dates, side="right")
            factors[np.asarray(indices)] = suffix_products[first_future_split]
    bars["cumulative_future_split_factor"] = factors
    for column in ("open", "high", "low", "close"):
        bars[f"split_adjusted_{column}"] = bars[column] / bars["cumulative_future_split_factor"]
    bars["split_adjusted_volume"] = bars["volume"] * bars["cumulative_future_split_factor"]
    bars["normalization_version"] = normalization_version
    bars["normalization_basis"] = basis
    bars["normalization_as_of"] = as_of
    keep = [
        "ticker", "trading_date", "provider", "schema_version", "ingested_at",
        "cumulative_future_split_factor", "split_adjusted_open", "split_adjusted_high",
        "split_adjusted_low", "split_adjusted_close", "split_adjusted_volume",
        "normalization_version", "normalization_basis", "normalization_as_of",
    ]
    return bars[keep]

def build_latest_basis_split_adjusted_series(
    raw_bars: pd.DataFrame,
    actions: pd.DataFrame,
    normalization_version: str = LATEST_BASIS_VERSION,
) -> pd.DataFrame:
    """Adjust all history to the latest known basis; not point-in-time safe.

    Internal convention: split_factor is new shares per old share. A 2:1 split is
    2.0 and a 1:2 reverse split is 0.5. The effective date contains post-split
    prices, so an action affects rows strictly before that date. Dividends are
    deliberately ignored.
    """
    return _apply_splits(raw_bars, _split_actions(actions), normalization_version, "latest")

def build_split_adjusted_series_as_of(
    raw_bars: pd.DataFrame,
    actions: pd.DataFrame,
    *,
    decision_date: date,
    decision_time: datetime,
    normalization_version: str = AS_OF_VERSION,
) -> pd.DataFrame:
    """Build a point-in-time-safe price history for one decision.

    Bars must have been available by decision_time. A split participates only
    when effective_date <= decision_date and available_at <= decision_time.
    Actions without availability metadata are conservatively excluded.
    """
    if decision_time.tzinfo is None:
        raise ValueError("decision_time must be timezone-aware")
    bars = raw_bars.copy()
    if not bars.empty:
        dates = pd.to_datetime(bars["trading_date"]).dt.date
        availability = pd.to_datetime(bars["available_at"], utc=True, errors="coerce")
        cutoff = pd.Timestamp(decision_time).tz_convert("UTC")
        bars = bars[(dates <= decision_date) & availability.notna() & (availability <= cutoff)]
    eligible = _split_actions(actions)
    if not eligible.empty:
        availability = pd.to_datetime(eligible["available_at"], utc=True, errors="coerce")
        cutoff = pd.Timestamp(decision_time).tz_convert("UTC")
        eligible = eligible[
            (eligible["effective_date"] <= decision_date)
            & availability.notna()
            & (availability <= cutoff)
        ]
    return _apply_splits(bars, eligible, normalization_version, "as_of", decision_time)

def build_split_adjusted_series(raw_bars: pd.DataFrame, actions: pd.DataFrame, normalization_version: str = LATEST_BASIS_VERSION) -> pd.DataFrame:
    """Backward-compatible alias for the explicitly latest-basis dataset."""
    return build_latest_basis_split_adjusted_series(raw_bars, actions, normalization_version)
