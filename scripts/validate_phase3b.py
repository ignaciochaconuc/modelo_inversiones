"""Validate sealed-test and artifact invariants for a completed Phase 3B run."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

ROOT = Path("data/reports/models/phase3b")


def main() -> int:
    global_manifest = json.loads((ROOT / "manifest.json").read_text(encoding="utf-8"))
    summary = json.loads((ROOT / "phase3b_summary.json").read_text(encoding="utf-8"))
    rows = pd.read_parquet(ROOT / "summary.parquet")
    if global_manifest.get("test_used") is not False or summary.get("test_used") is not False:
        raise ValueError("Phase 3B global artifacts must declare test_used=false")
    if rows.empty or rows["test_used"].ne(False).any():
        raise ValueError("experiment summary violates sealed-test mode")
    directories = [path for path in ROOT.iterdir() if path.is_dir()]
    if len(directories) != len(rows):
        raise ValueError("experiment directory count differs from summary")
    for directory in directories:
        manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
        metrics = json.loads((directory / "metrics.json").read_text(encoding="utf-8"))
        predictions = pd.read_parquet(directory / "validation_predictions.parquet")
        if manifest.get("test_used") is not False or manifest.get("mode") != "selection":
            raise ValueError(f"{directory.name} is not sealed-test selection output")
        dates = pd.to_datetime(predictions["decision_date"]).dt.date
        if dates.min().isoformat() < "2019-01-02" or dates.max().isoformat() > "2021-12-31":
            raise ValueError(f"{directory.name} predictions escape validation dates")
        if set(metrics.get("by_year", {})) != {"2019", "2020", "2021"}:
            raise ValueError(f"{directory.name} lacks validation-only yearly metrics")
        if predictions.duplicated(["ticker", "decision_date"]).any():
            raise ValueError(f"{directory.name} has duplicate predictions")
        if manifest["validation_rows"] != len(predictions):
            raise ValueError(f"{directory.name} row count differs from manifest")
    print(json.dumps({
        "status": "passed", "experiments": len(rows), "test_used": False,
        "validation_date_min": "2019-01-02", "validation_date_max": "2021-12-31",
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
