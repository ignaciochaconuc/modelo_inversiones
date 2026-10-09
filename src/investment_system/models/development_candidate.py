"""Frozen development-candidate contract and Phase 3D.7 evidence checks."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from investment_system.data.schemas.features import IDENTIFIER_COLUMNS, TARGET_COLUMNS
from investment_system.models.feature_ablations import FEATURE_FAMILIES
from investment_system.models.feature_sets import (
    QUANTITATIVE_BASELINE_FEATURES,
    QUANTITATIVE_BASELINE_VERSION,
)
from investment_system.models.nonlinear_profiles import TREE_PROFILES
from investment_system.models.tree_preprocessing import TREE_PREPROCESSING_VERSION

CANDIDATE_ID = "development-candidate-v1"
CANDIDATE_STATUS = "selected_for_final_holdout_evaluation"
CONSISTENCY_TOLERANCE = 1e-12
SEALED_TEST_START = "2022-01-03"
PURGE_RULE = (
    "decision_date < prediction_start and target_end_date_20d < prediction_start"
)


@dataclass(frozen=True)
class EvidencePaths:
    phase3b_summary: Path
    phase3c_summary: Path
    phase3c_candidate_manifest: Path
    phase3d_summary: Path
    phase3d5_summary: Path
    phase3d6_summary: Path

    def as_dict(self) -> dict[str, Path]:
        return {
            "phase3b": self.phase3b_summary,
            "phase3c": self.phase3c_summary,
            "phase3c_candidate": self.phase3c_candidate_manifest,
            "phase3d_1_4": self.phase3d_summary,
            "phase3d_5": self.phase3d5_summary,
            "phase3d_6": self.phase3d6_summary,
        }


def canonical_sha256(value: Any) -> str:
    """Hash stable JSON, independent of mapping insertion order."""
    encoded = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def feature_names_hash(features: tuple[str, ...] | list[str]) -> str:
    """Fingerprint the ordered feature allowlist."""
    return canonical_sha256(list(features))


def fingerprint_payload(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Select only frozen semantic fields; omit provenance and timestamps."""
    keys = (
        "task", "target", "horizon", "economic_use", "model_family", "model_profile",
        "hyperparameters", "feature_set_version", "ordered_feature_names", "preprocessing",
        "retraining_frequency", "training_window_policy", "training_history_start",
        "purge_rule", "random_state",
    )
    missing = [key for key in keys if key not in contract]
    if missing:
        raise ValueError(f"candidate contract lacks fingerprint fields: {missing}")
    return {key: contract[key] for key in keys}


def candidate_fingerprint(contract: Mapping[str, Any]) -> str:
    """Hash the immutable model procedure and specification."""
    return canonical_sha256(fingerprint_payload(contract))


def build_candidate_contract(
    *, universe_version: str, feature_schema_version: str,
    target_schema_version: str,
) -> dict[str, Any]:
    """Build the sole Phase 3D.7 candidate without fitting an estimator."""
    profile = next(item for item in TREE_PROFILES if item.profile_id == "rf-small")
    features = tuple(QUANTITATIVE_BASELINE_FEATURES)
    contract: dict[str, Any] = {
        "candidate_id": CANDIDATE_ID,
        "status": CANDIDATE_STATUS,
        "task": "regression",
        "target": "target_return_20d",
        "horizon": 20,
        "economic_use": "predicted future return -> cross-sectional percentile ranking",
        "model_family": "random_forest",
        "model_profile": "rf-small",
        "hyperparameters": dict(profile.parameters),
        "feature_set_version": QUANTITATIVE_BASELINE_VERSION,
        "feature_count": len(features),
        "ordered_feature_names": list(features),
        "feature_names_hash": feature_names_hash(features),
        "preprocessing_version": TREE_PREPROCESSING_VERSION,
        "preprocessing": {
            "version": TREE_PREPROCESSING_VERSION,
            "log1p_features": ["avg_dollar_volume_20d", "avg_dollar_volume_60d"],
            "imputation": "median_fit_on_current_train_only",
            "scaling": None,
            "winsorization": None,
            "pca": None,
            "adaptive_feature_selection": False,
            "all_na_train_behavior": "fail",
            "zero_variance_behavior": "detect_record_and_exclude",
        },
        "retraining_frequency": "annual",
        "training_window_policy": "expanding",
        "training_history_start": "2010-01-04",
        "purge_rule": PURGE_RULE,
        "purge_equality_behavior": "purge",
        "random_state": 42,
        "universe_version": universe_version,
        "feature_schema_version": str(feature_schema_version),
        "target_schema_version": target_schema_version,
        "selection_evidence_versions": {
            "phase3b": "3B-simple-predictive-baselines",
            "phase3c": "3C-nonlinear-predictive-models",
            "phase3d_1_4": "3D.1-3D.4",
            "phase3d_5": "3D.5",
            "phase3d_6": "3D.6",
        },
        "sealed_test_start": SEALED_TEST_START,
        "test_used": False,
        "test_opened": False,
    }
    contract["candidate_fingerprint"] = candidate_fingerprint(contract)
    return contract


def load_evidence(paths: EvidencePaths) -> dict[str, dict[str, Any]]:
    """Load only persisted development summaries/manifests, never data partitions."""
    loaded: dict[str, dict[str, Any]] = {}
    for name, path in paths.as_dict().items():
        if not path.is_file():
            raise FileNotFoundError(f"required Phase 3D.7 evidence artifact is missing: {path}")
        loaded[name] = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def _metric_vector(metrics: Mapping[str, Any]) -> dict[str, float]:
    rank = metrics["overall"]["ranking"]["rank_ic"]
    return {
        "mean_ic": float(rank["mean"]),
        "icir": float(rank["icir"]),
        "worst_year_ic": float(metrics["stability"]["worst_year_ic"]),
        "top10_uplift": float(
            metrics["overall"]["ranking"]["top10"]["average_top10_uplift"]
        ),
    }


def development_metrics_snapshot(phase3d5: Mapping[str, Any]) -> dict[str, Any]:
    """Extract the official pre-TEST snapshot from the approved full policy."""
    metrics = phase3d5["window_results"]["expanding"]["metrics"]
    rank = metrics["overall"]["ranking"]["rank_ic"]
    top10 = metrics["overall"]["ranking"]["top10"]
    return {
        "source": "Phase 3D.5 expanding; exactly reproduced by Phase 3D.6 full",
        "pseudo_oos_start": phase3d5["pseudo_oos_dates"][0],
        "pseudo_oos_nominal_end": phase3d5["pseudo_oos_dates"][1],
        "effective_label_safe_end": phase3d5["effective_label_safe_prediction_end"],
        "mean_rank_ic": rank["mean"],
        "median_rank_ic": rank["median"],
        "rank_ic_std": rank["std"],
        "icir": rank["icir"],
        "pct_positive_ic": rank["pct_positive"],
        "worst_year_ic": metrics["stability"]["worst_year_ic"],
        "best_year_ic": metrics["stability"]["best_year_ic"],
        "year_ic_std": metrics["stability"]["year_ic_std"],
        "positive_years": metrics["stability"]["positive_years"],
        "negative_years": metrics["stability"]["negative_years"],
        "top10_uplift": top10["average_top10_uplift"],
        "pct_positive_top10_uplift": top10["pct_dates_positive_uplift"],
        "test_used": False,
    }


def evidence_summary(artifacts: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    """Consolidate already-persisted selection evidence without new search."""
    b = artifacts["phase3b"]
    c = artifacts["phase3c"]
    d = artifacts["phase3d_1_4"]
    w = artifacts["phase3d_5"]
    a = artifacts["phase3d_6"]
    horizons: dict[str, Any] = {}
    for horizon in ("5d", "10d", "20d"):
        baseline = b["best_regression_model_by_horizon"][horizon]
        nonlinear = c["best_nonlinear_by_task_horizon"]["regression"][horizon]
        comparison = c["phase3b_comparisons"]["regression"][horizon]
        horizons[horizon] = {
            "phase3b_best": {
                key: baseline[key] for key in (
                    "experiment_id", "mean_ic", "icir", "pct_positive_ic", "top10_uplift"
                )
            },
            "phase3c_best": {
                key: nonlinear[key] for key in (
                    "experiment_id", "model_family", "profile", "mean_ic", "icir",
                    "pct_positive_ic", "worst_year_ic", "year_ic_std", "top10_uplift",
                )
            },
            "delta_nonlinear_vs_phase3b": {
                key: comparison[key] for key in (
                    "delta_mean_ic", "delta_icir", "delta_worst_year_ic",
                    "delta_top10_uplift", "material_improvement", "stability_improvement",
                )
            },
        }
    frequency = {
        name: {
            "mean_ic": values["overall"]["ranking"]["rank_ic"]["mean"],
            "icir": values["overall"]["ranking"]["rank_ic"]["icir"],
            "worst_year_ic": values["stability"]["worst_year_ic"],
            "top10_uplift": values["overall"]["ranking"]["top10"]["average_top10_uplift"],
            "retrain_count": values["operational_cost"]["number_of_retrains"],
        }
        for name, values in d["policy_results"]["rf-small"].items()
    }
    windows = {
        name: {
            **_metric_vector(values["metrics"]),
            "delta_mean_ic_vs_expanding": (
                0.0 if name == "expanding"
                else w["deltas_vs_expanding"][name]["delta_mean_ic_vs_expanding"]
            ),
        }
        for name, values in w["window_results"].items()
    }
    feature_rows = a["sorted_feature_family_contribution_table"]
    return {
        "decision_table": [
            {"dimension": "horizon", "alternatives_considered": ["5d", "10d", "20d"], "selected": "20d", "evidence_source": "Phase 3B + Phase 3C"},
            {"dimension": "model", "alternatives_considered": ["Ridge", "RF", "XGBoost", "LightGBM"], "selected": "RF-Small", "evidence_source": "Phase 3C + Phase 3D.1-3D.4"},
            {"dimension": "retraining_frequency", "alternatives_considered": ["monthly", "quarterly", "semiannual", "annual"], "selected": "annual", "evidence_source": "Phase 3D.1-3D.4"},
            {"dimension": "training_window", "alternatives_considered": ["expanding", "trailing-8y", "trailing-5y"], "selected": "expanding", "evidence_source": "Phase 3D.5"},
            {"dimension": "features", "alternatives_considered": ["full-52", "10 leave-one-family-out policies"], "selected": "full-52", "evidence_source": "Phase 3D.6"},
        ],
        "horizon_evidence": horizons,
        "model_evidence": {
            "fixed_validation_rf_20d": horizons["20d"]["phase3c_best"],
            "fixed_validation_delta_vs_phase3b": horizons["20d"]["delta_nonlinear_vs_phase3b"],
            "walkforward_rf_vs_ridge_annual": d["rf_vs_ridge_operational"],
        },
        "frequency_evidence": {
            "policies": frequency,
            "tolerance": d["retrain_ic_tolerance"],
            "selection": d["selected_operational_frequency"]["rf-small"],
        },
        "window_evidence": {
            "policies": windows,
            "selected": w["selected_window"],
            "concept_drift_interpretation": w["concept_drift_interpretation"],
        },
        "feature_evidence": {
            "full_reference": a["full_reference"],
            "family_contributions": feature_rows,
            "strongest_contributors": a["strongest_contributors"],
            "neutral_or_redundant_families": a["neutral_or_redundant_families"],
            "potentially_harmful_families": a["potentially_harmful_families"],
            "harmful_candidates": a["harmful_candidates"],
            "confirmation_subset_warranted": a["confirmation_subset_warranted"],
        },
        "test_used": False,
        "test_opened": False,
    }


def _check(
    name: str, expected: Any, observed: Any, *, tolerance: float | None = None,
) -> dict[str, Any]:
    if tolerance is not None and isinstance(expected, (int, float)) and isinstance(observed, (int, float)):
        difference = abs(float(observed) - float(expected))
        passed = difference <= tolerance
    else:
        difference = None
        passed = observed == expected
    display_expected = sorted(expected) if isinstance(expected, set) else expected
    display_observed = sorted(observed) if isinstance(observed, set) else observed
    return {
        "check": name, "expected": display_expected, "observed": display_observed,
        "absolute_difference": difference, "tolerance": tolerance, "passed": bool(passed),
    }


def consistency_checks(
    artifacts: Mapping[str, Mapping[str, Any]], contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate the complete evidence chain; readiness requires every check."""
    b = artifacts["phase3b"]
    c = artifacts["phase3c"]
    cm = artifacts["phase3c_candidate"]
    d = artifacts["phase3d_1_4"]
    w = artifacts["phase3d_5"]
    a = artifacts["phase3d_6"]
    profile = next(item for item in TREE_PROFILES if item.profile_id == "rf-small")
    horizon_rows = c.get("best_nonlinear_by_task_horizon", {}).get("regression", {})
    best_horizon_mean = max(horizon_rows, key=lambda name: horizon_rows[name]["mean_ic"])
    best_horizon_icir = max(horizon_rows, key=lambda name: horizon_rows[name]["icir"])
    best_horizon_worst = max(horizon_rows, key=lambda name: horizon_rows[name]["worst_year_ic"])
    persisted_family_union = {
        feature for values in a.get("feature_families", {}).values() for feature in values
    }
    checks = [
        _check("candidate_id", CANDIDATE_ID, contract.get("candidate_id")),
        _check("candidate_status", CANDIDATE_STATUS, contract.get("status")),
        _check("phase3c_candidate_exists", "rf-small-regression-20d-qbaselinev1-treeprepv1", cm.get("experiment_id")),
        _check("phase3c_candidate_task", "regression", cm.get("task")),
        _check("phase3c_candidate_target", "target_return_20d", cm.get("target_name")),
        _check("phase3c_candidate_horizon", 20, cm.get("horizon")),
        _check("phase3c_candidate_hyperparameters", profile.parameters, cm.get("model_hyperparameters")),
        _check("phase3c_candidate_preprocessing", TREE_PREPROCESSING_VERSION, cm.get("preprocessing_version")),
        _check("phase3c_selected_20d_identity", cm.get("experiment_id"), horizon_rows.get("20d", {}).get("experiment_id")),
        _check("horizon_best_mean_ic", "20d", best_horizon_mean),
        _check("horizon_best_icir", "20d", best_horizon_icir),
        _check("horizon_best_worst_year_ic", "20d", best_horizon_worst),
        _check("phase3d_selected_frequency", "annual", d.get("selected_operational_frequency", {}).get("rf-small", {}).get("selected_frequency")),
        _check("phase3d5_selected_window", "expanding", w.get("selected_window")),
        _check("phase3d6_feature_count", 52, a.get("full_feature_count")),
        _check("phase3d6_confirmation_not_warranted", False, a.get("confirmation_subset_warranted")),
        _check("phase3d6_no_harmful_candidates", [], a.get("harmful_candidates")),
        _check("contract_feature_count", 52, contract.get("feature_count")),
        _check("contract_ordered_features", list(QUANTITATIVE_BASELINE_FEATURES), contract.get("ordered_feature_names")),
        _check("feature_family_union", set(QUANTITATIVE_BASELINE_FEATURES), set(feature for values in FEATURE_FAMILIES.values() for feature in values)),
        _check("persisted_feature_family_union", set(QUANTITATIVE_BASELINE_FEATURES), persisted_family_union),
        _check("feature_target_disjoint", set(), set(QUANTITATIVE_BASELINE_FEATURES) & set(TARGET_COLUMNS)),
        _check("feature_identifier_disjoint", set(), set(QUANTITATIVE_BASELINE_FEATURES) & set(IDENTIFIER_COLUMNS)),
        _check("candidate_fingerprint", candidate_fingerprint(contract), contract.get("candidate_fingerprint")),
        _check("test_used_contract", False, contract.get("test_used")),
        _check("test_opened_contract", False, contract.get("test_opened")),
    ]
    for source, artifact in artifacts.items():
        checks.append(_check(f"{source}_test_used", False, artifact.get("test_used")))
    metrics = {
        "phase3d_1_4": _metric_vector(d["policy_results"]["rf-small"]["annual"]),
        "phase3d_5": _metric_vector(w["window_results"]["expanding"]["metrics"]),
        "phase3d_6": {
            "mean_ic": float(a["full_reference"]["mean_ic"]),
            "icir": float(a["full_reference"]["icir"]),
            "worst_year_ic": float(a["full_reference"]["worst_year_ic"]),
            "top10_uplift": float(a["full_reference"]["top10_uplift"]),
        },
    }
    reference = metrics["phase3d_1_4"]
    for source in ("phase3d_5", "phase3d_6"):
        for metric, expected in reference.items():
            checks.append(_check(
                f"reproduction_{source}_{metric}", expected, metrics[source][metric],
                tolerance=CONSISTENCY_TOLERANCE,
            ))
    schema_sources = (b, c, d, w, a)
    for index, artifact in enumerate(schema_sources, start=1):
        checks.append(_check(
            f"feature_schema_consistency_{index}", contract["feature_schema_version"],
            str(artifact.get("feature_schema_version")),
        ))
        checks.append(_check(
            f"target_schema_consistency_{index}", contract["target_schema_version"],
            artifact.get("target_schema_version"),
        ))
    failed = [item["check"] for item in checks if not item["passed"]]
    return {
        "tolerance": CONSISTENCY_TOLERANCE,
        "checks": checks,
        "reproduction_chain": metrics,
        "passed": not failed,
        "failed_checks": failed,
        "test_used": False,
        "test_opened": False,
    }
