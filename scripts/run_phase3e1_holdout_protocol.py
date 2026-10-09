"""Freeze Phase 3E.1 from candidate/config metadata without opening TEST."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from investment_system.models.holdout_protocol import (
    PRIMARY_METRIC,
    build_holdout_protocol,
    build_snapshot_contract,
    holdout_controls,
    holdout_threshold_contract,
    protocol_consistency_checks,
)

CANDIDATE_PATH = Path(
    "data/reports/models/phase3d/final_candidate/candidate_contract.json"
)
OUTPUT_ROOT = Path("data/reports/models/phase3e/protocol")
CONFIG_PATHS = (
    Path("config/settings.yaml"),
    Path("config/universe.yaml"),
    Path("config/provider_symbols.yaml"),
    Path("config/corporate_action_overrides.yaml"),
)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"required frozen contract is missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _file_sha256(path: Path) -> str:
    if not path.is_file():
        raise FileNotFoundError(f"required snapshot configuration is missing: {path}")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8",
    )
    temporary.replace(path)


def freeze_protocol(
    *, candidate_path: Path = CANDIDATE_PATH,
    output_root: Path = OUTPUT_ROOT,
    config_paths: tuple[Path, ...] = CONFIG_PATHS,
) -> dict[str, Any]:
    """Freeze protocol artifacts using only one candidate JSON and YAML metadata."""
    candidate = _read_json(candidate_path)
    config_hashes = {path.as_posix(): _file_sha256(path) for path in config_paths}
    universe_path = next(
        (path for path in config_paths if path.as_posix().endswith("config/universe.yaml")),
        None,
    )
    if universe_path is None:
        raise ValueError("config/universe.yaml is required for the nominal cutoff")
    universe_config = yaml.safe_load(universe_path.read_text(encoding="utf-8"))
    nominal_cutoff = str(universe_config["universe"]["as_of"])
    expected_universe = (
        f"{universe_config['universe_type']}:"
        f"{universe_config['universe']['name']}:{nominal_cutoff}"
    )
    if candidate.get("universe_version") != expected_universe:
        raise ValueError(
            "configured universe metadata differs from the frozen candidate identity"
        )

    snapshot = build_snapshot_contract(
        candidate,
        nominal_date_cutoff=nominal_cutoff,
        config_hashes=config_hashes,
    )
    protocol = build_holdout_protocol(candidate, snapshot)
    checks = protocol_consistency_checks(candidate, snapshot, protocol)
    if not checks["passed"]:
        raise ValueError(f"protocol readiness failed: {checks['failed_checks']}")

    thresholds = holdout_threshold_contract()
    controls = holdout_controls()
    summary = {
        "phase": "3E.1",
        "protocol_id": protocol["protocol_id"],
        "protocol_status": protocol["protocol_status"],
        "candidate_id": candidate["candidate_id"],
        "candidate_fingerprint": candidate["candidate_fingerprint"],
        "holdout_protocol_fingerprint": protocol["holdout_protocol_fingerprint"],
        "data_snapshot_fingerprint": snapshot["data_snapshot_fingerprint"],
        "primary_metric": PRIMARY_METRIC,
        "thresholds": thresholds,
        "controls": controls,
        "one_shot_policy": protocol["one_shot_policy"],
        "ready_to_open_test": True,
        "test_used": False,
        "test_opened": False,
        "holdout_executed": False,
        "phase3e2_started": False,
    }
    artifacts = {
        "holdout_protocol.json": protocol,
        "holdout_thresholds.json": thresholds,
        "holdout_controls.json": controls,
        "snapshot_contract.json": snapshot,
        "protocol_consistency_checks.json": checks,
        "phase3e1_summary.json": summary,
    }
    for name, artifact in artifacts.items():
        _write_json(output_root / name, artifact)
    return summary


def main() -> int:
    summary = freeze_protocol()
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
