"""Validate the frozen Phase 3E.1 protocol without accessing any dataset."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

import yaml

from investment_system.models.holdout_protocol import (
    EXCLUDED_PORTFOLIO_METRICS,
    PRIMARY_METRIC,
    SECONDARY_METRICS,
    build_holdout_protocol,
    build_snapshot_contract,
    data_snapshot_fingerprint,
    holdout_controls,
    holdout_protocol_fingerprint,
    holdout_threshold_contract,
    protocol_consistency_checks,
)

OUTPUT_ROOT = Path("data/reports/models/phase3e/protocol")
CANDIDATE_PATH = Path(
    "data/reports/models/phase3d/final_candidate/candidate_contract.json"
)
CONFIG_PATHS = (
    Path("config/settings.yaml"),
    Path("config/universe.yaml"),
    Path("config/provider_symbols.yaml"),
    Path("config/corporate_action_overrides.yaml"),
)
REQUIRED_ARTIFACTS = {
    "holdout_protocol.json",
    "holdout_thresholds.json",
    "holdout_controls.json",
    "snapshot_contract.json",
    "protocol_consistency_checks.json",
    "phase3e1_summary.json",
}


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required Phase 3E.1 artifact is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _has_mapping_key(value: Any, forbidden_key: str) -> bool:
    if isinstance(value, Mapping):
        return forbidden_key in value or any(
            _has_mapping_key(item, forbidden_key) for item in value.values()
        )
    if isinstance(value, list):
        return any(_has_mapping_key(item, forbidden_key) for item in value)
    return False


def main() -> int:
    actual_files = {path.name for path in OUTPUT_ROOT.iterdir() if path.is_file()}
    if actual_files != REQUIRED_ARTIFACTS:
        raise ValueError(
            f"Phase 3E.1 artifact set differs: expected={sorted(REQUIRED_ARTIFACTS)}, "
            f"observed={sorted(actual_files)}"
        )
    candidate = _read_json(CANDIDATE_PATH)
    protocol = _read_json(OUTPUT_ROOT / "holdout_protocol.json")
    thresholds = _read_json(OUTPUT_ROOT / "holdout_thresholds.json")
    controls = _read_json(OUTPUT_ROOT / "holdout_controls.json")
    snapshot = _read_json(OUTPUT_ROOT / "snapshot_contract.json")
    persisted_checks = _read_json(OUTPUT_ROOT / "protocol_consistency_checks.json")
    summary = _read_json(OUTPUT_ROOT / "phase3e1_summary.json")

    config_hashes = {
        path.as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in CONFIG_PATHS
    }
    universe = yaml.safe_load(Path("config/universe.yaml").read_text(encoding="utf-8"))
    nominal_cutoff = str(universe["universe"]["as_of"])
    expected_snapshot = build_snapshot_contract(
        candidate,
        nominal_date_cutoff=nominal_cutoff,
        config_hashes=config_hashes,
    )
    expected_protocol = build_holdout_protocol(candidate, expected_snapshot)
    expected_checks = protocol_consistency_checks(
        candidate, expected_snapshot, expected_protocol,
    )

    if snapshot != expected_snapshot:
        raise ValueError("snapshot contract is not reproducible from permitted metadata")
    if snapshot["data_snapshot_fingerprint"] != data_snapshot_fingerprint(snapshot):
        raise ValueError("snapshot fingerprint is not reproducible")
    if protocol != expected_protocol:
        raise ValueError("holdout protocol differs from the canonical frozen contract")
    if protocol["holdout_protocol_fingerprint"] != holdout_protocol_fingerprint(protocol):
        raise ValueError("holdout protocol fingerprint is not reproducible")
    if persisted_checks != expected_checks or not persisted_checks["passed"]:
        raise ValueError("persisted protocol consistency checks differ or failed")
    if thresholds != holdout_threshold_contract():
        raise ValueError("thresholds or boundary semantics differ")
    if controls != holdout_controls():
        raise ValueError("authorized controls differ")
    if protocol["metrics"]["primary"] != PRIMARY_METRIC:
        raise ValueError("primary metric differs")
    if protocol["metrics"]["secondary"] != SECONDARY_METRICS:
        raise ValueError("secondary metric definitions are incomplete")
    if protocol["metrics"]["portfolio_metrics_excluded"] != EXCLUDED_PORTFOLIO_METRICS:
        raise ValueError("portfolio metric exclusions differ")
    if protocol["evaluation_procedure"] != expected_protocol["evaluation_procedure"]:
        raise ValueError("annual/expanding/purge procedure differs")
    if protocol["one_shot_policy"] != expected_protocol["one_shot_policy"]:
        raise ValueError("one-shot policy differs")

    expected_summary_fields = {
        "phase": "3E.1",
        "protocol_id": protocol["protocol_id"],
        "protocol_status": protocol["protocol_status"],
        "candidate_id": candidate["candidate_id"],
        "candidate_fingerprint": candidate["candidate_fingerprint"],
        "holdout_protocol_fingerprint": protocol["holdout_protocol_fingerprint"],
        "data_snapshot_fingerprint": snapshot["data_snapshot_fingerprint"],
        "ready_to_open_test": True,
        "test_used": False,
        "test_opened": False,
        "holdout_executed": False,
        "phase3e2_started": False,
    }
    for key, expected in expected_summary_fields.items():
        if summary.get(key) != expected:
            raise ValueError(f"summary invariant failed: {key}")
    for artifact in (protocol, thresholds, controls, snapshot, persisted_checks, summary):
        if _has_mapping_key(artifact, "opened_at"):
            raise ValueError("3E.1 artifact contains an opened_at value")

    forbidden_names = {
        "holdout_predictions.parquet", "holdout_metrics.json", "test_predictions",
        "test_annual_results.json",
    }
    all_paths = [path for path in OUTPUT_ROOT.rglob("*") if path.is_file()]
    if any(path.name.lower() in forbidden_names for path in all_paths):
        raise ValueError("TEST result artifact exists in the protocol directory")
    forbidden_extensions = {".parquet", ".pkl", ".pickle", ".joblib", ".csv"}
    if any(path.suffix.lower() in forbidden_extensions for path in all_paths):
        raise ValueError("prediction, fitted-model, or tabular result artifact exists")

    print(json.dumps({
        "status": "passed",
        "checks": len(expected_checks["checks"]),
        "protocol_id": protocol["protocol_id"],
        "protocol_status": protocol["protocol_status"],
        "holdout_protocol_fingerprint": protocol["holdout_protocol_fingerprint"],
        "data_snapshot_fingerprint": snapshot["data_snapshot_fingerprint"],
        "ready_to_open_test": True,
        "test_used": False,
        "test_opened": False,
        "holdout_executed": False,
        "phase3e2_started": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
