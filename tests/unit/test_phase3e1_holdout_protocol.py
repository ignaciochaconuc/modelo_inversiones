from copy import deepcopy
from pathlib import Path

import pytest

from investment_system.models.development_candidate import build_candidate_contract
from investment_system.models.holdout_protocol import (
    AUTHORIZED_CANDIDATE_FINGERPRINT,
    NOMINAL_TEST_START,
    PROTOCOL_ID,
    PROTOCOL_STATUS,
    build_holdout_protocol,
    build_snapshot_contract,
    classify_absolute_holdout,
    classify_rf_vs_ridge,
    data_snapshot_fingerprint,
    holdout_protocol_fingerprint,
    is_exact_reproduction,
    protocol_consistency_checks,
)


def _candidate() -> dict:
    candidate = build_candidate_contract(
        universe_version="development_fixed:sp100_development:2026-10-05",
        feature_schema_version="4",
        target_schema_version="corporate-action-safe-target-v3",
    )
    candidate.update({
        "final_model_fitted": False,
        "production_ready": False,
        "approved_for_trading": False,
    })
    return candidate


def _snapshot(candidate: dict | None = None) -> dict:
    return build_snapshot_contract(
        candidate or _candidate(),
        nominal_date_cutoff="2026-10-05",
        config_hashes={
            "config/corporate_action_overrides.yaml": "6f1dc6653cd8dbc689fd3d384f388f4c887282771e5017c0bbd5d0724b073ac4",
            "config/provider_symbols.yaml": "e8f8c047392c0e4ea18c1094880f024e1351c26e2a6b131dfb607f16bf2d391d",
            "config/settings.yaml": "972e9a85537592387e5580294e1f602d4c8b5f105dbc4e6466ce5b99c3495d69",
            "config/universe.yaml": "b66702dd3e8e3de9bfa139571e46d2174b4d2ad35d1dc8bac2958b38bc4a355f",
        },
    )


def _protocol() -> dict:
    candidate = _candidate()
    return build_holdout_protocol(candidate, _snapshot(candidate))


def test_protocol_freezes_exact_candidate_and_walkforward_identity() -> None:
    candidate = _candidate()
    snapshot = _snapshot(candidate)
    protocol = build_holdout_protocol(candidate, snapshot)
    assert candidate["candidate_fingerprint"] == AUTHORIZED_CANDIDATE_FINGERPRINT
    assert protocol["protocol_id"] == PROTOCOL_ID
    assert protocol["protocol_status"] == PROTOCOL_STATUS
    assert protocol["test_range"]["nominal_test_start"] == NOMINAL_TEST_START
    assert protocol["test_range"]["nominal_test_end"] == "2026-10-05"
    assert protocol["evaluation_procedure"]["retraining_frequency"] == "annual"
    assert protocol["evaluation_procedure"]["training_window_policy"] == "expanding"
    assert protocol["evaluation_procedure"]["single_static_2010_2021_model_for_all_test_years"] is False
    assert protocol["test_used"] is False
    assert protocol["test_opened"] is False
    assert protocol["holdout_executed"] is False
    checks = protocol_consistency_checks(candidate, snapshot, protocol)
    assert checks["passed"] is True
    assert not checks["failed_checks"]


def test_protocol_and_snapshot_fingerprints_are_canonical_and_semantic() -> None:
    candidate = _candidate()
    snapshot = _snapshot(candidate)
    protocol = build_holdout_protocol(candidate, snapshot)
    expected = holdout_protocol_fingerprint(protocol)
    assert holdout_protocol_fingerprint(dict(reversed(list(protocol.items())))) == expected
    provenance = {
        **protocol, "generated_at": "later", "git_commit": "abc", "fit_seconds": 42,
    }
    assert holdout_protocol_fingerprint(provenance) == expected
    snapshot_provenance = {**snapshot, "generated_at": "later", "git_commit": "abc"}
    assert data_snapshot_fingerprint(snapshot_provenance) == snapshot["data_snapshot_fingerprint"]

    mutations = []
    changed = deepcopy(protocol)
    changed["threshold_contract"]["thresholds"]["pass_ic_threshold"] = 0.031
    mutations.append(changed)
    changed = deepcopy(protocol)
    changed["metrics"]["secondary"]["ranking"].append("new_metric")
    mutations.append(changed)
    changed = deepcopy(protocol)
    changed["authorized_candidate"]["candidate_fingerprint"] = "0" * 64
    mutations.append(changed)
    changed = deepcopy(protocol)
    changed["evaluation_procedure"]["purge_rule"] = "different"
    mutations.append(changed)
    for changed in mutations:
        assert holdout_protocol_fingerprint(changed) != expected

    changed_snapshot = deepcopy(snapshot)
    changed_snapshot["nominal_date_cutoff"] = "2026-10-02"
    assert data_snapshot_fingerprint(changed_snapshot) != snapshot["data_snapshot_fingerprint"]


@pytest.mark.parametrize(
    ("mean_ic", "expected"),
    [
        (-0.001, "hard_fail"), (0.0, "hard_fail"), (0.005, "fail"),
        (0.009999, "fail"), (0.01, "marginal"), (0.029999, "marginal"),
        (0.03, "pass"), (0.05, "pass"),
    ],
)
def test_absolute_mean_ic_boundaries(mean_ic: float, expected: str) -> None:
    assert classify_absolute_holdout(
        mean_rank_ic=mean_ic,
        worst_year_ic=0.0,
        positive_years=1,
        evaluable_years=2,
        top10_uplift=0.01,
    ) == expected


def test_absolute_stability_top10_and_year_share_boundaries() -> None:
    common = {"mean_rank_ic": 0.03, "positive_years": 1, "evaluable_years": 2}
    assert classify_absolute_holdout(**common, worst_year_ic=-0.01, top10_uplift=0.01) == "marginal"
    assert classify_absolute_holdout(**common, worst_year_ic=-0.009999, top10_uplift=0.01) == "pass"
    assert classify_absolute_holdout(**common, worst_year_ic=0.0, top10_uplift=-0.001) == "marginal"
    assert classify_absolute_holdout(**common, worst_year_ic=0.0, top10_uplift=0.0) == "marginal"
    assert classify_absolute_holdout(**common, worst_year_ic=0.0, top10_uplift=0.001) == "pass"
    assert classify_absolute_holdout(
        mean_rank_ic=0.03, worst_year_ic=0.0, positive_years=1,
        evaluable_years=3, top10_uplift=0.01,
    ) == "marginal"
    assert classify_absolute_holdout(
        mean_rank_ic=0.03, worst_year_ic=0.0, positive_years=2,
        evaluable_years=3, top10_uplift=0.01,
    ) == "pass"
    assert classify_absolute_holdout(
        mean_rank_ic=0.02, worst_year_ic=0.0, positive_years=1,
        evaluable_years=2, top10_uplift=0.0,
    ) == "fail"


@pytest.mark.parametrize(
    ("delta", "expected"),
    [
        (-0.004, "ridge_outperforms_rf"), (-0.003, "approximately_equal"),
        (0.0, "approximately_equal"), (0.003, "approximately_equal"),
        (0.004, "rf_outperforms_ridge"),
    ],
)
def test_relative_rf_ridge_boundaries(delta: float, expected: str) -> None:
    assert classify_rf_vs_ridge(
        rf_mean_rank_ic=0.05 + delta, ridge_mean_rank_ic=0.05,
    ) == expected


def test_one_shot_initial_state_and_exact_reproduction_policy() -> None:
    protocol = _protocol()
    policy = protocol["one_shot_policy"]
    assert policy["holdout_opened"] is False
    assert policy["holdout_executed"] is False
    assert "opened_at" not in policy
    reference = {
        "candidate_fingerprint": "a", "holdout_protocol_fingerprint": "b",
        "data_snapshot_fingerprint": "c", "test_start": "2022-01-03",
        "nominal_test_end": "2026-10-05", "effective_test_end": "2026-09-04",
    }
    assert is_exact_reproduction(reference, deepcopy(reference)) is True
    for key in reference:
        changed = deepcopy(reference)
        changed[key] = "different"
        assert is_exact_reproduction(reference, changed) is False


def test_phase3e1_contract_module_has_no_test_data_or_training_dependency() -> None:
    source = Path("src/investment_system/models/holdout_protocol.py").read_text(
        encoding="utf-8",
    )
    forbidden_imports = (
        "import pandas", "import numpy", "FeatureStore", "TargetStore",
        "read_parquet", "SupervisedDatasetBuilder", ".fit(", ".predict(",
    )
    assert all(token not in source for token in forbidden_imports)
