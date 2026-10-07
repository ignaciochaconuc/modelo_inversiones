"""Feature-store-only equal-weight and momentum baseline strategies."""
from __future__ import annotations

from datetime import date
import math

import pandas as pd

from investment_system.backtesting.schemas import TargetAllocation
from investment_system.backtesting.strategies.base import StrategyPlan, decision_time
from investment_system.data.calendar import TradingCalendar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.universe import UniverseConfig


class _CrossSectionalFeatures:
    def __init__(
        self,
        feature_store: QuantitativeFeatureStore,
        universe: UniverseConfig,
        calendar: TradingCalendar,
        *,
        timezone_name: str = "America/New_York",
        decision_cutoff: str = "20:15",
    ) -> None:
        self.feature_store = feature_store
        self.universe = universe
        self.calendar = calendar
        self.timezone_name = timezone_name
        self.decision_cutoff = decision_cutoff

    def _rows(self, start: date, end: date, columns: list[str]) -> pd.DataFrame:
        rows = self.feature_store.read_feature_range(
            start,
            end,
            columns=["decision_time", "model_eligible", *columns],
            tickers=self.universe.tickers,
        )
        if rows.empty:
            return rows
        rows = rows.copy()
        rows["ticker"] = rows["ticker"].astype(str).str.upper()
        rows["decision_date"] = pd.to_datetime(rows["decision_date"]).dt.date
        duplicates = rows.duplicated(["ticker", "decision_date"], keep=False)
        if duplicates.any():
            keys = rows.loc[duplicates, ["ticker", "decision_date"]].to_dict("records")
            raise ValueError(f"duplicate feature rows for strategy decisions: {keys[:5]}")
        for row in rows.itertuples(index=False):
            if not self.calendar.is_session(row.decision_date):
                raise ValueError(f"feature decision_date is not a session: {row.decision_date}")
            expected = pd.Timestamp(self._generated_at(row.decision_date)).tz_convert("UTC")
            actual = pd.to_datetime(row.decision_time, utc=True, errors="coerce")
            if pd.isna(actual) or actual != expected:
                raise ValueError(
                    f"feature decision_time mismatch for {row.ticker} on {row.decision_date}"
                )
        return rows.sort_values(["decision_date", "ticker"]).reset_index(drop=True)

    def _generated_at(self, session: date):
        return decision_time(
            session,
            timezone_name=self.timezone_name,
            cutoff=self.decision_cutoff,
        )

    @staticmethod
    def _eligible(rows: pd.DataFrame) -> pd.DataFrame:
        mask = rows["model_eligible"].notna() & rows["model_eligible"].eq(True)
        return rows[mask].copy()


class EqualWeightStrategy(_CrossSectionalFeatures):
    strategy_name = "equal_weight"
    strategy_version = "equal-weight-v1"

    def generate_allocations(self, start: date, end: date) -> StrategyPlan:
        rows = self._rows(start, end, [])
        allocations: dict[date, TargetAllocation] = {}
        counts: dict[date, int] = {}
        for session, day_rows in rows.groupby("decision_date", sort=True):
            eligible = self._eligible(day_rows)
            tickers = sorted(eligible["ticker"].tolist())
            counts[session] = len(tickers)
            weights = (
                {ticker: 1.0 / len(tickers) for ticker in tickers}
                if tickers else {}
            )
            allocations[session] = TargetAllocation(
                generated_at=self._generated_at(session),
                weights=weights,
                cash_weight=0.0 if weights else 1.0,
            )
        return StrategyPlan(
            strategy_name=self.strategy_name,
            strategy_version=self.strategy_version,
            allocations=allocations,
            eligible_assets_by_date=counts,
        )


class SimpleMomentumStrategy(_CrossSectionalFeatures):
    strategy_name = "momentum_20d_top10"
    strategy_version = "momentum-20d-top10-v1"
    maximum_positions = 10
    position_weight = 0.10

    def generate_allocations(self, start: date, end: date) -> StrategyPlan:
        rows = self._rows(start, end, ["momentum_20d"])
        allocations: dict[date, TargetAllocation] = {}
        counts: dict[date, int] = {}
        for session, day_rows in rows.groupby("decision_date", sort=True):
            eligible = self._eligible(day_rows)
            momentum = pd.to_numeric(eligible["momentum_20d"], errors="coerce")
            eligible = eligible[momentum.notna() & momentum.map(math.isfinite)].copy()
            eligible["momentum_20d"] = pd.to_numeric(
                eligible["momentum_20d"], errors="raise",
            )
            ranked = eligible.sort_values(
                ["momentum_20d", "ticker"],
                ascending=[False, True],
                kind="mergesort",
            )
            selected = ranked.head(self.maximum_positions)["ticker"].tolist()
            counts[session] = len(eligible)
            weights = {ticker: self.position_weight for ticker in selected}
            allocations[session] = TargetAllocation(
                generated_at=self._generated_at(session),
                weights=weights,
                cash_weight=1.0 - self.position_weight * len(selected),
            )
        return StrategyPlan(
            strategy_name=self.strategy_name,
            strategy_version=self.strategy_version,
            allocations=allocations,
            eligible_assets_by_date=counts,
        )
