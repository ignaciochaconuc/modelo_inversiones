from copy import deepcopy
import json

import pytest

from investment_system.models.development_candidate import (
    CANDIDATE_ID,
    CANDIDATE_STATUS,
    EvidencePaths,
    build_candidate_contract,
    candidate_fingerprint,
    consistency_checks,
    evidence_summary,
    feature_names_hash,
    load_evidence,
)
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.feature_ablations import FEATURE_FAMILIES


def _metrics(mean: float = 0.06, icir: float = 0.3, worst: float = 0.02, top10: float = 0.01) -> dict:
    return {
        "overall": {"ranking": {
            "rank_ic": {"mean": mean, "median": mean, "std": 0.2, "icir": icir, "pct_positive": 0.6},
            "top10": {"average_top10_uplift": top10, "pct_dates_positive_uplift": 0.65},
        }},
        "stability": {
            "worst_year_ic": worst, "best_year_ic": 0.1, "year_ic_std": 0.03,
            "positive_years": 6, "negative_years": 0,
        },
        "operational_cost": {"number_of_retrains": 6},
    }


def _candidate_row(horizon: str, mean: float) -> dict:
    return {
        "experiment_id": f"rf-small-regression-{horizon}-qbaselinev1-treeprepv1",
        "model_family": "rf", "profile": "small", "mean_ic": mean,
        "icir": mean * 4, "pct_positive_ic": 0.6, "worst_year_ic": mean / 2,
        "year_ic_std": 0.03, "top10_uplift": mean / 4,
    }


def _artifacts() -> dict:
    rf_parameters = {
        "n_estimators": 300, "max_depth": 4, "min_samples_leaf": 100,
        "max_features": "sqrt", "bootstrap": True, "random_state": 42, "n_jobs": -1,
    }
    schemas = {
        "feature_schema_version": "4",
        "target_schema_version": "corporate-action-safe-target-v3",
        "test_used": False,
    }
    phase3b = {
        **schemas,
        "best_regression_model_by_horizon": {
            horizon: {
                "experiment_id": f"ridge-regression-{horizon}", "mean_ic": mean / 2,
                "icir": mean * 2, "pct_positive_ic": 0.52, "top10_uplift": mean / 8,
            }
            for horizon, mean in (("5d", 0.02), ("10d", 0.04), ("20d", 0.06))
        },
    }
    comparisons = {
        horizon: {
            "delta_mean_ic": mean / 2, "delta_icir": mean * 2,
            "delta_worst_year_ic": mean / 4, "delta_top10_uplift": mean / 8,
            "material_improvement": True, "stability_improvement": True,
        }
        for horizon, mean in (("5d", 0.02), ("10d", 0.04), ("20d", 0.06))
    }
    phase3c = {
        **schemas,
        "best_nonlinear_by_task_horizon": {"regression": {
            horizon: _candidate_row(horizon, mean)
            for horizon, mean in (("5d", 0.02), ("10d", 0.04), ("20d", 0.06))
        }},
        "phase3b_comparisons": {"regression": comparisons},
    }
    frequency_metrics = {
        name: {**_metrics(mean), "operational_cost": {"number_of_retrains": count}}
        for name, mean, count in (
            ("monthly", 0.059, 72), ("quarterly", 0.0595, 24),
            ("semiannual", 0.058, 12), ("annual", 0.06, 6),
        )
    }
    phase3d = {
        **schemas,
        "retrain_ic_tolerance": 0.003,
        "policy_results": {"rf-small": frequency_metrics},
        "selected_operational_frequency": {"rf-small": {
            "selected_frequency": "annual", "raw_best_frequency": "annual",
        }},
        "rf_vs_ridge_operational": {"rf_mean_ic": 0.06, "ridge_mean_ic": 0.02},
    }
    phase3d5 = {
        **schemas,
        "pseudo_oos_dates": ["2016-01-01", "2021-12-31"],
        "effective_label_safe_prediction_end": "2021-12-02",
        "window_results": {
            "expanding": {"metrics": _metrics()},
            "trailing-8y": {"metrics": _metrics(0.058)},
            "trailing-5y": {"metrics": _metrics(0.055)},
        },
        "deltas_vs_expanding": {
            "trailing-8y": {"delta_mean_ic_vs_expanding": -0.002},
            "trailing-5y": {"delta_mean_ic_vs_expanding": -0.005},
        },
        "selected_window": "expanding",
        "concept_drift_interpretation": {"concept_drift_evidence": False},
    }
    full = {
        "ablation_policy": "full", "removed_family": None, "requested_feature_count": 52,
        "mean_ic": 0.06, "median_ic": 0.06, "icir": 0.3, "pct_positive_ic": 0.6,
        "worst_year_ic": 0.02, "best_year_ic": 0.1, "year_ic_std": 0.03,
        "positive_years": 6, "negative_years": 0, "top10_uplift": 0.01,
        "pct_dates_positive_uplift": 0.65,
    }
    phase3d6 = {
        **schemas,
        "pseudo_oos_dates": ["2016-01-01", "2021-12-31"],
        "effective_label_safe_prediction_end": "2021-12-02",
        "full_feature_count": 52, "full_reference": full,
        "feature_families": {name: list(values) for name, values in FEATURE_FAMILIES.items()},
        "sorted_feature_family_contribution_table": [],
        "strongest_contributors": ["volatility"],
        "neutral_or_redundant_families": [], "potentially_harmful_families": [],
        "harmful_candidates": [], "confirmation_subset_warranted": False,
    }
    return {
        "phase3b": phase3b,
        "phase3c": phase3c,
        "phase3c_candidate": {
            **schemas,
            "experiment_id": "rf-small-regression-20d-qbaselinev1-treeprepv1",
            "task": "regression", "target_name": "target_return_20d", "horizon": 20,
            "model_hyperparameters": rf_parameters,
            "preprocessing_version": "tree-preprocessing-v1",
        },
        "phase3d_1_4": phase3d,
        "phase3d_5": phase3d5,
        "phase3d_6": phase3d6,
    }


def _contract() -> dict:
    return build_candidate_contract(
        universe_version="development_fixed:synthetic:2026-01-01",
        feature_schema_version="4",
        target_schema_version="corporate-action-safe-target-v3",
    )


def test_candidate_contract_freezes_exact_expected_specification() -> None:
    contract = _contract()
    assert contract["candidate_id"] == CANDIDATE_ID
    assert contract["status"] == CANDIDATE_STATUS
    assert contract["task"] == "regression"
    assert contract["target"] == "target_return_20d"
    assert contract["horizon"] == 20
    assert contract["model_profile"] == "rf-small"
    assert contract["hyperparameters"] == {
        "n_estimators": 300, "max_depth": 4, "min_samples_leaf": 100,
        "max_features": "sqrt", "bootstrap": True, "random_state": 42, "n_jobs": -1,
    }
    assert contract["feature_count"] == 52
    assert contract["ordered_feature_names"] == list(QUANTITATIVE_BASELINE_FEATURES)
    assert contract["retraining_frequency"] == "annual"
    assert contract["training_window_policy"] == "expanding"
    assert contract["preprocessing_version"] == "tree-preprocessing-v1"
    assert contract["test_used"] is False and contract["test_opened"] is False


def test_fingerprint_is_canonical_sensitive_to_semantics_and_ignores_provenance() -> None:
    contract = _contract()
    expected = candidate_fingerprint(contract)
    reversed_order = dict(reversed(list(contract.items())))
    assert candidate_fingerprint(reversed_order) == expected
    provenance = {**contract, "generated_at": "tomorrow", "git_commit": "abc", "fit_seconds": 99}
    assert candidate_fingerprint(provenance) == expected
    for path, value in (
        (("ordered_feature_names",), list(reversed(contract["ordered_feature_names"]))),
        (("hyperparameters", "max_depth"), 5),
        (("horizon",), 10),
        (("retraining_frequency",), "monthly"),
    ):
        changed = deepcopy(contract)
        if len(path) == 1:
            changed[path[0]] = value
        else:
            changed[path[0]][path[1]] = value
        assert candidate_fingerprint(changed) != expected
    assert contract["feature_names_hash"] == feature_names_hash(QUANTITATIVE_BASELINE_FEATURES)


def test_evidence_parser_consolidates_only_predeclared_decisions() -> None:
    evidence = evidence_summary(_artifacts())
    assert [row["selected"] for row in evidence["decision_table"]] == [
        "20d", "RF-Small", "annual", "expanding", "full-52",
    ]
    assert evidence["horizon_evidence"]["20d"]["phase3c_best"]["mean_ic"] == 0.06
    assert evidence["frequency_evidence"]["selection"]["selected_frequency"] == "annual"
    assert evidence["window_evidence"]["selected"] == "expanding"
    assert evidence["feature_evidence"]["confirmation_subset_warranted"] is False
    assert evidence["test_used"] is False and evidence["test_opened"] is False


def test_cross_phase_consistency_passes_only_for_complete_frozen_chain() -> None:
    artifacts = _artifacts()
    contract = _contract()
    result = consistency_checks(artifacts, contract)
    assert result["passed"] is True
    assert not result["failed_checks"]
    mutations = (
        ("phase3d_5", lambda value: value["window_results"]["expanding"]["metrics"]["overall"]["ranking"]["rank_ic"].__setitem__("mean", 0.07)),
        ("phase3c_candidate", lambda value: value["model_hyperparameters"].__setitem__("max_depth", 5)),
        ("phase3d_6", lambda value: value.__setitem__("full_feature_count", 51)),
        ("phase3d_6", lambda value: value.__setitem__("confirmation_subset_warranted", True)),
        ("phase3d_6", lambda value: value.__setitem__("test_used", True)),
    )
    for source, mutate in mutations:
        changed = deepcopy(artifacts)
        mutate(changed[source])
        assert consistency_checks(changed, contract)["passed"] is False


def test_load_evidence_fails_on_missing_artifact_without_data_partitions(tmp_path) -> None:
    existing = tmp_path / "evidence.json"
    existing.write_text(json.dumps({"test_used": False}), encoding="utf-8")
    paths = EvidencePaths(existing, existing, existing, existing, existing, tmp_path / "missing.json")
    with pytest.raises(FileNotFoundError, match="required Phase 3D.7 evidence"):
        load_evidence(paths)
