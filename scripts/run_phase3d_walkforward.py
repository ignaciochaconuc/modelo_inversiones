"""Execute Phase 3D.1-3D.4 on existing real data without opening TEST."""
from __future__ import annotations

from dataclasses import asdict
from datetime import date
import json
from pathlib import Path
from typing import Any

import pandas as pd

from investment_system.core.config import load_settings
from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.data.storage.feature_store import QuantitativeFeatureStore
from investment_system.data.universe import load_universe
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.walkforward import (
    ELIGIBILITY_COLUMN,
    FREQUENCIES,
    RANK_COLUMN,
    SEALED_TEST_START,
    TARGET_COLUMN,
    TARGET_END_COLUMN,
    WALKFORWARD_START,
    Phase3DWalkForwardRunner,
    build_walkforward_frame,
    compact_policy_row,
    compare_models,
    select_operational_frequency,
)

OUTPUT_ROOT = Path("data/reports/models/phase3d")
MODELS = ("rf-small", "ridge-100")
RUN_ORDER = ("annual", "semiannual", "quarterly", "monthly")


def _years(files: list[Path], first: int, last: int) -> list[Path]:
    return [path for path in files if first <= int(path.parent.name.split("=")[1]) <= last]


def _read_features(files: list[Path]) -> pd.DataFrame:
    columns = [
        "ticker", "decision_date", "model_eligible", "feature_corporate_action_contaminated",
        *QUANTITATIVE_BASELINE_FEATURES,
    ]
    return pd.concat([pd.read_parquet(path, columns=columns) for path in files], ignore_index=True)


def _read_label_safe_targets(files: list[Path]) -> pd.DataFrame:
    columns = [
        "ticker", "decision_date", TARGET_COLUMN, RANK_COLUMN,
        TARGET_END_COLUMN, ELIGIBILITY_COLUMN,
    ]
    return pd.concat([
        pd.read_parquet(
            path, columns=columns,
            filters=[(TARGET_END_COLUMN, "<", SEALED_TEST_START)],
        ) for path in files
    ], ignore_index=True)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def _age_finding(metrics: dict[str, Any]) -> dict[str, Any]:
    buckets = metrics["model_age"]
    available = [
        (name, values) for name, values in buckets.items()
        if values["rows"] and values["rank_ic"] and values["rank_ic"]["mean"] is not None
    ]
    first_name, first = available[0]
    last_name, last = available[-1]
    means = [float(values["rank_ic"]["mean"]) for _, values in available]
    delta = float(last["rank_ic"]["mean"] - first["rank_ic"]["mean"])
    monotonic_decline = all(current <= previous for previous, current in zip(means, means[1:]))
    monotonic_improvement = all(current >= previous for previous, current in zip(means, means[1:]))
    if monotonic_decline and delta <= -0.005:
        interpretation = "clear_monotonic_degradation"
    elif monotonic_improvement and delta >= 0.005:
        interpretation = "clear_monotonic_improvement"
    elif delta <= -0.005:
        interpretation = "non_monotonic_oldest_lower"
    elif delta >= 0.005:
        interpretation = "non_monotonic_oldest_higher"
    else:
        interpretation = "non_monotonic_no_material_endpoint_change"
    return {
        "youngest_bucket": first_name, "youngest_mean_ic": first["rank_ic"]["mean"],
        "oldest_observed_bucket": last_name, "oldest_mean_ic": last["rank_ic"]["mean"],
        "oldest_decision_dates": last["decision_dates"],
        "delta_oldest_vs_youngest_ic": delta, "interpretation": interpretation,
        "monotonic_decline": monotonic_decline,
        "monotonic_improvement": monotonic_improvement,
        "interpretive_threshold": 0.005,
    }


def main() -> int:
    settings = load_settings()
    universe = load_universe()
    store = QuantitativeFeatureStore(settings.paths.features, settings.paths.features.parent / "targets")
    feature_files = _years(sorted(store.features.glob("year=*/data.parquet")), 2010, 2021)
    target_files = _years(sorted(store.targets.glob("year=*/data.parquet")), 2010, 2021)
    if not feature_files or not target_files:
        raise ValueError("Phase 3D requires existing 2010-2021 Feature and Target Stores")
    features = _read_features(feature_files)
    targets = _read_label_safe_targets(target_files)
    frame = build_walkforward_frame(features, targets)
    effective_end = max(frame.loc[frame["decision_date"] >= WALKFORWARD_START, "decision_date"])
    runner = Phase3DWalkForwardRunner(
        OUTPUT_ROOT, XNYSTradingCalendar(),
        feature_schema_version=settings.features.schema_version,
        target_schema_version=settings.features.target_version,
    )
    all_predictions: list[pd.DataFrame] = []
    all_fits: list[pd.DataFrame] = []
    all_preprocessing: list[pd.DataFrame] = []
    all_metrics: dict[str, dict[str, dict[str, Any]]] = {model: {} for model in MODELS}

    def progress(row: dict[str, Any]) -> None:
        print(json.dumps({
            "fit_id": row["fit_id"], "fit_seconds": round(row["fit_seconds"], 3),
            "rows_after_purge": row["rows_after_purge"], "test_used": False,
        }), flush=True)

    for model in MODELS:
        for frequency in RUN_ORDER:
            predictions, fits, preprocessing, metrics = runner.run_policy(
                frame, model, frequency, progress=progress,
            )
            policy_root = OUTPUT_ROOT / "policies" / model / frequency
            policy_root.mkdir(parents=True, exist_ok=True)
            predictions.to_parquet(policy_root / "walkforward_predictions.parquet", index=False)
            fits.to_parquet(policy_root / "fits.parquet", index=False)
            preprocessing.to_parquet(policy_root / "fit_preprocessing.parquet", index=False)
            _write_json(policy_root / "metrics.json", metrics)
            all_predictions.append(predictions)
            all_fits.append(fits)
            all_preprocessing.append(preprocessing)
            all_metrics[model][frequency] = metrics
            print(json.dumps({
                "policy_complete": f"{model}/{frequency}", "retrainings": len(fits),
                "mean_ic": metrics["overall"]["ranking"]["rank_ic"]["mean"],
                "test_used": False,
            }), flush=True)

    predictions = pd.concat(all_predictions, ignore_index=True)
    fits = pd.concat(all_fits, ignore_index=True)
    preprocessing = pd.concat(all_preprocessing, ignore_index=True)
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    predictions.to_parquet(OUTPUT_ROOT / "walkforward_predictions.parquet", index=False)
    fits.to_parquet(OUTPUT_ROOT / "fits.parquet", index=False)
    preprocessing.to_parquet(OUTPUT_ROOT / "fit_preprocessing.parquet", index=False)
    _write_json(OUTPUT_ROOT / "policy_metrics.json", all_metrics)

    selections = {
        model: select_operational_frequency(model, all_metrics[model]) for model in MODELS
    }
    same_frequency = {
        frequency: compare_models(frequency, frequency, all_metrics) for frequency in FREQUENCIES
    }
    operational = compare_models(
        selections["rf-small"].selected_frequency,
        selections["ridge-100"].selected_frequency,
        all_metrics,
    )
    model_age = {
        model: {
            "selected_frequency": selections[model].selected_frequency,
            "metrics": all_metrics[model][selections[model].selected_frequency]["model_age"],
            "finding": _age_finding(all_metrics[model][selections[model].selected_frequency]),
            "aggregation_note": "selected policy only; frequencies are not pooled as independent observations",
        } for model in MODELS
    }
    _write_json(OUTPUT_ROOT / "model_age_metrics.json", {
        "by_policy": {
            model: {frequency: values["model_age"] for frequency, values in policies.items()}
            for model, policies in all_metrics.items()
        },
        "selected_policy_by_model": model_age,
        "test_used": False,
    })
    summary_rows = [
        compact_policy_row(model, frequency, all_metrics[model][frequency])
        for model in MODELS for frequency in FREQUENCIES
    ]
    summary_frame = pd.DataFrame(summary_rows)
    summary_frame.to_csv(OUTPUT_ROOT / "summary.csv", index=False)
    summary_frame.to_parquet(OUTPUT_ROOT / "summary.parquet", index=False)
    manifest = runner.global_manifest(effective_prediction_end=effective_end)
    summary = {
        **manifest,
        "policy_count": 8, "fit_count": int(len(fits)),
        "prediction_rows": int(len(predictions)),
        "policy_results": all_metrics,
        "selected_operational_frequency": {
            model: asdict(selection) for model, selection in selections.items()
        },
        "rf_vs_ridge_same_frequency": same_frequency,
        "rf_vs_ridge_operational": operational,
        "model_age_findings": model_age,
        "test_used": False,
    }
    _write_json(OUTPUT_ROOT / "manifest.json", manifest)
    _write_json(OUTPUT_ROOT / "phase3d_walkforward_summary.json", summary)
    print(json.dumps({
        "status": "passed", "policies": 8, "fits": len(fits),
        "prediction_rows": len(predictions), "effective_prediction_end": str(effective_end),
        "selected": {model: selection.selected_frequency for model, selection in selections.items()},
        "test_used": False,
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
