import json

from scripts.run_phase3e1_holdout_protocol import CONFIG_PATHS, freeze_protocol

from investment_system.models.development_candidate import build_candidate_contract


def test_protocol_freeze_needs_only_candidate_and_configuration_metadata(tmp_path) -> None:
    candidate = build_candidate_contract(
        universe_version="development_fixed:sp100_development:2026-10-05",
        feature_schema_version="4",
        target_schema_version="corporate-action-safe-target-v3",
    )
    candidate["final_model_fitted"] = False
    candidate_path = tmp_path / "candidate_contract.json"
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")

    output_root = tmp_path / "reports" / "phase3e" / "protocol"
    summary = freeze_protocol(
        candidate_path=candidate_path,
        output_root=output_root,
        config_paths=CONFIG_PATHS,
    )

    assert summary["ready_to_open_test"] is True
    assert summary["test_used"] is False
    assert summary["test_opened"] is False
    assert summary["holdout_executed"] is False
    assert not (tmp_path / "data" / "features").exists()
    assert not (tmp_path / "data" / "targets").exists()
    assert {path.name for path in output_root.iterdir()} == {
        "holdout_protocol.json", "holdout_thresholds.json", "holdout_controls.json",
        "snapshot_contract.json", "protocol_consistency_checks.json",
        "phase3e1_summary.json",
    }
