"""Freeze Phase 3D.7 from persisted development evidence; never load TEST data."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

import pandas as pd

from investment_system.core.reproducibility import git_metadata
from investment_system.data.universe import load_universe
from investment_system.models.development_candidate import (
    EvidencePaths,
    build_candidate_contract,
    consistency_checks,
    development_metrics_snapshot,
    evidence_summary,
    load_evidence,
)

OUTPUT_ROOT = Path("data/reports/models/phase3d/final_candidate")
EVIDENCE_PATHS = EvidencePaths(
    phase3b_summary=Path("data/reports/models/phase3b/phase3b_summary.json"),
    phase3c_summary=Path("data/reports/models/phase3c/phase3c_summary.json"),
    phase3c_candidate_manifest=Path(
        "data/reports/models/phase3c/"
        "rf-small-regression-20d-qbaselinev1-treeprepv1/manifest.json"
    ),
    phase3d_summary=Path("data/reports/models/phase3d/phase3d_walkforward_summary.json"),
    phase3d5_summary=Path(
        "data/reports/models/phase3d/window_sensitivity/phase3d_window_summary.json"
    ),
    phase3d6_summary=Path(
        "data/reports/models/phase3d/feature_ablations/phase3d_feature_ablation_summary.json"
    ),
)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, default=str), encoding="utf-8")
    temporary.replace(path)


def _selection_rows(evidence: dict[str, Any]) -> list[dict[str, Any]]:
    supporting = {
        "horizon": evidence["horizon_evidence"],
        "model": evidence["model_evidence"],
        "retraining_frequency": evidence["frequency_evidence"],
        "training_window": evidence["window_evidence"],
        "features": evidence["feature_evidence"],
    }
    return [
        {
            **row,
            "alternatives_considered": json.dumps(row["alternatives_considered"]),
            "supporting_metrics": json.dumps(supporting[row["dimension"]], sort_keys=True),
            "test_used": False,
            "test_opened": False,
        }
        for row in evidence["decision_table"]
    ]


def main() -> int:
    artifacts = load_evidence(EVIDENCE_PATHS)
    universe = load_universe()
    phase3d6 = artifacts["phase3d_6"]
    universe_version = (
        f"{universe.universe_type}:{universe.universe.name}:{universe.universe.as_of}"
    )
    contract = build_candidate_contract(
        universe_version=universe_version,
        feature_schema_version=str(phase3d6["feature_schema_version"]),
        target_schema_version=phase3d6["target_schema_version"],
    )
    checks = consistency_checks(artifacts, contract)
    if not checks["passed"]:
        _write_json(OUTPUT_ROOT / "consistency_failure.json", {
            "phase": "3D-final-development-candidate-selection",
            "scope": "3D.7",
            "candidate_frozen": False,
            "consistency_checks": checks,
            "test_used": False,
            "test_opened": False,
        })
        raise RuntimeError(f"candidate freeze blocked: {checks['failed_checks']}")

    generated_at = datetime.now(timezone.utc).isoformat()
    contract = {
        **contract,
        "frozen_at": generated_at,
        **git_metadata(),
        "final_model_fitted": False,
        "production_ready": False,
        "approved_for_trading": False,
    }
    evidence = evidence_summary(artifacts)
    metrics = development_metrics_snapshot(artifacts["phase3d_5"])
    source_paths = {name: str(path) for name, path in EVIDENCE_PATHS.as_dict().items()}
    summary = {
        "phase": "3D-final-development-candidate-selection",
        "scope": "3D.7",
        "candidate_id": contract["candidate_id"],
        "candidate_status": contract["status"],
        "candidate_fingerprint": contract["candidate_fingerprint"],
        "selected_specification": contract,
        "evidence_sources": source_paths,
        "key_development_metrics": metrics,
        "consistency_status": checks["passed"],
        "failed_checks": checks["failed_checks"],
        "test_used": False,
        "test_opened": False,
        "ready_for_holdout_evaluation": checks["passed"],
        "final_model_fitted": False,
        "portfolio_backtest_run": False,
        "next_phase_started": False,
        "generated_at": generated_at,
        **git_metadata(),
    }
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    _write_json(OUTPUT_ROOT / "candidate_contract.json", contract)
    _write_json(OUTPUT_ROOT / "evidence_summary.json", {
        **evidence, "evidence_sources": source_paths, "generated_at": generated_at,
    })
    _write_json(OUTPUT_ROOT / "development_metrics.json", metrics)
    _write_json(OUTPUT_ROOT / "consistency_checks.json", checks)
    _write_json(OUTPUT_ROOT / "phase3d_final_candidate_summary.json", summary)
    pd.DataFrame(_selection_rows(evidence)).to_csv(
        OUTPUT_ROOT / "selection_evidence.csv", index=False,
    )
    print(json.dumps({
        "status": "passed",
        "candidate_id": contract["candidate_id"],
        "candidate_status": contract["status"],
        "candidate_fingerprint": contract["candidate_fingerprint"],
        "checks": len(checks["checks"]),
        "ready_for_holdout_evaluation": checks["passed"],
        "final_model_fitted": False,
        "test_used": False,
        "test_opened": False,
    }, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
