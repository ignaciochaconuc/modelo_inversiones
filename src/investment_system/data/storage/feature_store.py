import json
from datetime import date
from pathlib import Path
from typing import Any
import pandas as pd

from investment_system.data.schemas.features import TARGET_COLUMNS

class QuantitativeFeatureStore:
    """Separate yearly datasets with upsert and authoritative range rebuild APIs."""
    def __init__(self, features_root: str | Path, targets_root: str | Path | None = None) -> None:
        root = Path(features_root)
        self.features = root / "quantitative"
        self.targets = Path(targets_root) / "quantitative" if targets_root else root.parent / "targets" / "quantitative"
        self.features.mkdir(parents=True, exist_ok=True)
        self.targets.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _write_atomic(frame: pd.DataFrame, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(".tmp.parquet")
        frame.to_parquet(temporary, index=False)
        temporary.replace(path)

    @staticmethod
    def _upsert_dataset(root: Path, frame: pd.DataFrame) -> None:
        if frame.empty:
            return
        dates = pd.to_datetime(frame["decision_date"])
        for year, incoming in frame.groupby(dates.dt.year):
            path = root / f"year={year}" / "data.parquet"
            existing = pd.read_parquet(path) if path.exists() else pd.DataFrame()
            combined = pd.concat([existing, incoming], ignore_index=True)
            combined = combined.drop_duplicates(["ticker", "decision_date"], keep="last").sort_values(["decision_date", "ticker"])
            QuantitativeFeatureStore._write_atomic(combined, path)

    @staticmethod
    def _replace_range(root: Path, frame: pd.DataFrame, tickers: list[str], start_date: date, end_date: date) -> None:
        """Authoritatively replace selected ticker/date keys, removing stale rows."""
        incoming_dates = pd.to_datetime(frame["decision_date"]) if not frame.empty else pd.Series(dtype="datetime64[ns]")
        for year in range(start_date.year, end_date.year + 1):
            path = root / f"year={year}" / "data.parquet"
            existing = pd.read_parquet(path) if path.exists() else pd.DataFrame()
            if not existing.empty:
                dates = pd.to_datetime(existing["decision_date"]).dt.date
                stale = existing["ticker"].isin(tickers) & (dates >= start_date) & (dates <= end_date)
                existing = existing[~stale]
            incoming = frame[incoming_dates.dt.year == year] if not frame.empty else frame
            combined = pd.concat([existing, incoming], ignore_index=True)
            if not combined.empty:
                combined = combined.drop_duplicates(["ticker", "decision_date"], keep="last").sort_values(["decision_date", "ticker"])
                QuantitativeFeatureStore._write_atomic(combined, path)
            elif path.exists():
                path.unlink()

    def write_features(self, frame: pd.DataFrame) -> None:
        self._upsert_dataset(self.features, frame)

    def write_targets(self, frame: pd.DataFrame) -> None:
        self._upsert_dataset(self.targets, frame)

    def replace_feature_range(self, frame: pd.DataFrame, tickers: list[str], start_date: date, end_date: date) -> None:
        self._replace_range(self.features, frame, tickers, start_date, end_date)

    def replace_target_range(self, frame: pd.DataFrame, tickers: list[str], start_date: date, end_date: date) -> None:
        self._replace_range(self.targets, frame, tickers, start_date, end_date)

    def read_features(self) -> pd.DataFrame:
        files = list(self.features.glob("year=*/data.parquet"))
        return pd.concat([pd.read_parquet(path) for path in files], ignore_index=True) if files else pd.DataFrame()

    def read_feature_range(
        self,
        start_date: date,
        end_date: date,
        *,
        columns: list[str],
        tickers: list[str] | None = None,
    ) -> pd.DataFrame:
        """Read selected feature-only columns for an inclusive decision range."""
        if start_date > end_date:
            raise ValueError("start_date must be <= end_date")
        requested = list(dict.fromkeys(("ticker", "decision_date", *columns)))
        forbidden = sorted(set(requested).intersection(TARGET_COLUMNS))
        if forbidden:
            raise ValueError(f"target columns cannot be read as strategy features: {forbidden}")
        frames: list[pd.DataFrame] = []
        for year in range(start_date.year, end_date.year + 1):
            path = self.features / f"year={year}" / "data.parquet"
            if path.exists():
                frames.append(pd.read_parquet(path, columns=requested))
        if not frames:
            return pd.DataFrame(columns=requested)
        result = pd.concat(frames, ignore_index=True)
        dates = pd.to_datetime(result["decision_date"]).dt.date
        result = result[(dates >= start_date) & (dates <= end_date)]
        if tickers is not None:
            result = result[result["ticker"].isin(tickers)]
        return result.sort_values(["decision_date", "ticker"]).reset_index(drop=True)

    def read_targets(self) -> pd.DataFrame:
        files = list(self.targets.glob("year=*/data.parquet"))
        return pd.concat([pd.read_parquet(path) for path in files], ignore_index=True) if files else pd.DataFrame()

    def write_manifest(self, manifest: dict[str, Any]) -> Path:
        path = self.features / "manifest.json"
        path.write_text(json.dumps(manifest, indent=2, default=str), encoding="utf-8")
        return path

    def write_report(self, report: dict[str, Any]) -> Path:
        path = self.features / "build_report.json"
        path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
        return path
