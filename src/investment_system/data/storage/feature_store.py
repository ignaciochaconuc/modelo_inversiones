import json
from pathlib import Path
from typing import Any
import pandas as pd

class QuantitativeFeatureStore:
    """Separate, year-partitioned feature and target Parquet datasets."""
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

    def write_features(self, frame: pd.DataFrame) -> None:
        self._upsert_dataset(self.features, frame)

    def write_targets(self, frame: pd.DataFrame) -> None:
        self._upsert_dataset(self.targets, frame)

    def read_features(self) -> pd.DataFrame:
        files = list(self.features.glob("year=*/data.parquet"))
        return pd.concat([pd.read_parquet(path) for path in files], ignore_index=True) if files else pd.DataFrame()

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
