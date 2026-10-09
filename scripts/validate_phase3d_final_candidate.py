"""Validate the frozen Phase 3D.7 development candidate without opening TEST."""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from investment_system.models.development_candidate import (
    CANDIDATE_ID,
    CANDIDATE_STATUS,
    PURGE_RULE,
    candidate_fingerprint,
    consistency_checks,
    development_metrics_snapshot,
    feature_names_hash,
    load_evidence,
)
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.nonlinear_profiles import TREE_PROFILES
from run_phase3d_final_candidate import EVIDENCE_PATHS, OUTPUT_ROOT

EXPECTED_RF = next(item.parameters for item in TREE_PROFILES if item.profile_id == "rf-small")


def main() -> int:
    contract = json.loads((OUTPUT_ROOT / "candidate_contract.json").read_text(encoding="utf-8"))
    evidence = json.loads((OUTPUT_ROOT / "evidence_summary.json").read_text(encoding="utf-8"))
    metrics = json.loads((OUTPUT_ROOT / "development_metrics.json").read_text(encoding="utf-8"))
    persisted_checks = json.loads(
        (OUTPUT_ROOT / "consistency_checks.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (OUTPUT_ROOT / "phase3d_final_candidate_summary.json").read_text(encoding="utf-8")
    )
    selection = pd.read_csv(OUTPUT_ROOT / "selection_evidence.csv")
    artifacts = load_evidence(EVIDENCE_PATHS)
    if contract.get("candidate_id") != CANDIDATE_ID:
        raise ValueError("incorrect candidate_id")
    if contract.get("status") != CANDIDATE_STATUS:
        raise ValueError("incorrect candidate status")
    if contract.get("task") != "regression" or contract.get("target") != "target_return_20d":
        raise ValueError("candidate task/target differs from freeze")
    if contract.get("horizon") != 20:
        raise ValueError("candidate horizon differs from freeze")
    if contract.get("model_family") != "random_forest" or contract.get("model_profile") != "rf-small":
        raise ValueError("candidate model differs from RF-Small")
    if contract.get("hyperparameters") != EXPECTED_RF:
        raise ValueError("candidate RF parameters differ from frozen profile")
    if contract.get("feature_set_version") != "quantitative-baseline-v1":
        raise ValueError("candidate feature-set version differs")
    if contract.get("feature_count") != 52:
        raise ValueError("candidate must contain 52 features")
    if contract.get("ordered_feature_names") != list(QUANTITATIVE_BASELINE_FEATURES):
        raise ValueError("candidate ordered features differ from canonical allowlist")
    if contract.get("feature_names_hash") != feature_names_hash(QUANTITATIVE_BASELINE_FEATURES):
        raise ValueError("feature hash is not reproducible")
    if contract.get("candidate_fingerprint") != candidate_fingerprint(contract):
        raise ValueError("candidate fingerprint is not reproducible")
    if contract.get("preprocessing_version") != "tree-preprocessing-v1":
        raise ValueError("candidate preprocessing version differs")
    preprocessing = contract.get("preprocessing", {})
    if preprocessing != {
        "version": "tree-preprocessing-v1",
        "log1p_features": ["avg_dollar_volume_20d", "avg_dollar_volume_60d"],
        "imputation": "median_fit_on_current_train_only",
        "scaling": None,
        "winsorization": None,
        "pca": None,
        "adaptive_feature_selection": False,
        "all_na_train_behavior": "fail",
        "zero_variance_behavior": "detect_record_and_exclude",
    }:
        raise ValueError("candidate preprocessing semantics differ")
    if contract.get("retraining_frequency") != "annual":
        raise ValueError("candidate frequency differs from annual")
    if contract.get("training_window_policy") != "expanding":
        raise ValueError("candidate window differs from expanding")
    if contract.get("training_history_start") != "2010-01-04":
        raise ValueError("candidate historical start differs")
    if contract.get("purge_rule") != PURGE_RULE:
        raise ValueError("candidate purge rule differs")
    if contract.get("test_used") is not False or contract.get("test_opened") is not False:
        raise ValueError("candidate contract violates sealed TEST")
    if contract.get("final_model_fitted") is not False:
        raise ValueError("Phase 3D.7 must not fit a final model")
    recomputed_checks = consistency_checks(artifacts, contract)
    if not recomputed_checks["passed"] or recomputed_checks["failed_checks"]:
        raise ValueError(f"cross-phase consistency failed: {recomputed_checks['failed_checks']}")
    if persisted_checks["checks"] != recomputed_checks["checks"]:
        raise ValueError("persisted checks differ from independent recomputation")
    expected_metrics = development_metrics_snapshot(artifacts["phase3d_5"])
    if metrics != expected_metrics:
        raise ValueError("development performance snapshot differs from approved evidence")
    if artifacts["phase3d_6"].get("confirmation_subset_warranted") is not False:
        raise ValueError("a Phase 3D.6.1 confirmation remains warranted")
    if artifacts["phase3d_6"].get("harmful_candidates") != []:
        raise ValueError("harmful feature candidates remain unresolved")
    if len(selection) != 5 or set(selection["dimension"]) != {
        "horizon", "model", "retraining_frequency", "training_window", "features",
    }:
        raise ValueError("selection evidence table is incomplete")
    if selection["test_used"].ne(False).any() or selection["test_opened"].ne(False).any():
        raise ValueError("selection evidence violates sealed TEST")
    if evidence.get("test_used") is not False or evidence.get("test_opened") is not False:
        raise ValueError("evidence summary violates sealed TEST")
    if summary.get("scope") != "3D.7" or summary.get("candidate_id") != CANDIDATE_ID:
        raise ValueError("final summary identity differs")
    if summary.get("candidate_fingerprint") != contract["candidate_fingerprint"]:
        raise ValueError("summary candidate fingerprint differs")
    if summary.get("consistency_status") is not True:
        raise ValueError("summary consistency status is not passed")
    if summary.get("ready_for_holdout_evaluation") is not True:
        raise ValueError("candidate is not ready for future holdout evaluation")
    for name in (
        "test_used", "test_opened", "final_model_fitted",
        "portfolio_backtest_run", "next_phase_started",
    ):
        if summary.get(name) is not False:
            raise ValueError(f"summary invariant failed: {name}")
    forbidden_extensions = {".pkl", ".pickle", ".joblib", ".parquet"}
    if any(path.suffix.lower() in forbidden_extensions for path in OUTPUT_ROOT.rglob("*")):
        raise ValueError("final candidate directory contains fitted-model or prediction artifacts")
    if any("test" in path.name.lower() for path in OUTPUT_ROOT.rglob("*") if path.is_file()):
        raise ValueError("TEST-named artifact found in Phase 3D.7 output")
    candidate_contracts = list(OUTPUT_ROOT.glob("candidate_contract*.json"))
    if len(candidate_contracts) != 1:
        raise ValueError("candidate_id is not represented by exactly one contract")
    print(json.dumps({
        "status": "passed",
        "candidate_id": contract["candidate_id"],
        "candidate_fingerprint": contract["candidate_fingerprint"],
        "checks": len(recomputed_checks["checks"]),
        "ready_for_holdout_evaluation": True,
        "test_used": False,
        "test_opened": False,
        "final_model_fitted": False,
    }))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
