"""Pure contracts for freezing the Phase 3E.1 final-holdout protocol.

This module intentionally has no market-data, feature-store, target-store, model-fit,
or prediction dependencies.  Phase 3E.1 freezes semantics; it does not execute them.
"""
from __future__ import annotations

import math
from typing import Any, Mapping

from investment_system.models.development_candidate import (
    CANDIDATE_ID,
    CANDIDATE_STATUS,
    PURGE_RULE,
    candidate_fingerprint,
    canonical_sha256,
    feature_names_hash,
)
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES

PROTOCOL_ID = "holdout-protocol-v1"
PROTOCOL_VERSION = "1"
PROTOCOL_STATUS = "frozen_pending_execution"
AUTHORIZED_CANDIDATE_FINGERPRINT = (
    "65bbec61f8fda0df24097267b777c882fec4410cecbeb89ff909622a1f8ef467"
)
AUTHORIZED_HOLDOUT_PROTOCOL_FINGERPRINT = (
    "7b9c9fbef617ede2bc1e78cec3fb35ddfc5b2b13d049f189e088c03fa37032e6"
)
AUTHORIZED_DATA_SNAPSHOT_FINGERPRINT = (
    "2fa2ccc185c11d734aaf8e2ffbe0ee149425651a804200022b7aac734b3b3b6f"
)
NOMINAL_TEST_START = "2022-01-03"
TRAINING_HISTORY_START = "2010-01-04"

PASS_IC_THRESHOLD = 0.03
MARGINAL_IC_THRESHOLD = 0.01
WORST_YEAR_PASS_FLOOR = -0.01
POSITIVE_YEAR_SHARE_FLOOR = 0.50
RF_RIDGE_IC_EQUIVALENCE_TOLERANCE = 0.003

EXPECTED_RF_PARAMETERS = {
    "n_estimators": 300,
    "max_depth": 4,
    "min_samples_leaf": 100,
    "max_features": "sqrt",
    "bootstrap": True,
    "random_state": 42,
    "n_jobs": -1,
}

PRIMARY_METRIC = {
    "metric_id": "mean_daily_cross_sectional_rank_ic",
    "definition": "mean of daily cross-sectional Spearman rank correlations",
    "prediction": "predicted target_return_20d",
    "actual": "target_return_20d",
}

SECONDARY_METRICS = {
    "ranking": [
        "mean_rank_ic", "median_rank_ic", "rank_ic_std", "icir",
        "pct_positive_rank_ic",
    ],
    "regression": ["mae", "rmse", "pooled_pearson", "pooled_spearman", "daily_pearson"],
    "top10_diagnostic": [
        "average_top10_actual_future_return",
        "average_universe_actual_future_return",
        "top10_uplift",
        "pct_dates_positive_uplift",
    ],
    "annual_stability": [
        "mean_rank_ic", "median_rank_ic", "icir", "pct_positive_ic",
        "top10_uplift", "decision_date_count", "partial_year",
    ],
    "cross_year_stability": [
        "worst_year_ic", "best_year_ic", "year_ic_std", "positive_years",
        "negative_years",
    ],
    "development_comparison_diagnostics": [
        "holdout_mean_ic_divided_by_development_mean_ic",
        "delta_holdout_vs_development",
    ],
}

EXCLUDED_PORTFOLIO_METRICS = [
    "cagr", "portfolio_sharpe", "portfolio_max_drawdown", "portfolio_nav",
    "transaction_costs", "turnover", "allocation_rules",
]

THRESHOLDS = {
    "pass_ic_threshold": PASS_IC_THRESHOLD,
    "marginal_ic_threshold": MARGINAL_IC_THRESHOLD,
    "worst_year_pass_floor": WORST_YEAR_PASS_FLOOR,
    "positive_year_share_floor": POSITIVE_YEAR_SHARE_FLOOR,
    "rf_ridge_ic_equivalence_tolerance": RF_RIDGE_IC_EQUIVALENCE_TOLERANCE,
}

BOUNDARY_SEMANTICS = {
    "mean_rank_ic_equal_0": "hard_fail",
    "mean_rank_ic_equal_0_01": "not_fail_by_ic_alone; eligible_for_marginal",
    "mean_rank_ic_equal_0_03": "eligible_for_pass",
    "worst_year_ic_equal_minus_0_01": "not_pass; pass comparison is strict",
    "positive_year_share_equal_0_50": "satisfies_pass_share_condition",
    "top10_uplift_equal_0": "not_pass",
    "rf_ridge_delta_equal_plus_or_minus_0_003": "approximately_equal",
}

ABSOLUTE_CLASSIFICATION_RULES = {
    "precedence": ["hard_fail", "fail", "pass", "marginal"],
    "hard_fail": "mean_rank_ic <= 0",
    "fail": (
        "0 < mean_rank_ic < 0.01, or top10_uplift <= 0 and "
        "mean_rank_ic < 0.03"
    ),
    "pass": (
        "mean_rank_ic >= 0.03 and worst_year_ic > -0.01 and "
        "positive_years / evaluable_years >= 0.50 and top10_uplift > 0"
    ),
    "marginal": "not hard_fail, fail, or pass",
    "evaluable_years": "years with an evaluable sample only",
}

RELATIVE_CLASSIFICATION_RULES = {
    "delta": "rf_mean_rank_ic - ridge_mean_rank_ic",
    "rf_outperforms_ridge": "delta > 0.003",
    "ridge_outperforms_rf": "delta < -0.003",
    "approximately_equal": "-0.003 <= delta <= 0.003",
    "changes_absolute_status": False,
}


def snapshot_fingerprint_payload(contract: Mapping[str, Any]) -> dict[str, Any]:
    """Return only immutable snapshot identity fields."""
    keys = (
        "snapshot_contract_version", "universe_version", "feature_schema_version",
        "target_schema_version", "market_data_snapshot", "nominal_date_cutoff",
        "relevant_config_hashes", "candidate_fingerprint",
    )
    missing = [key for key in keys if key not in contract]
    if missing:
        raise ValueError(f"snapshot contract lacks fingerprint fields: {missing}")
    return {key: contract[key] for key in keys}


def data_snapshot_fingerprint(contract: Mapping[str, Any]) -> str:
    """Hash snapshot metadata without inspecting any dataset rows."""
    return canonical_sha256(snapshot_fingerprint_payload(contract))


def build_snapshot_contract(
    candidate: Mapping[str, Any], *, nominal_date_cutoff: str,
    config_hashes: Mapping[str, str],
) -> dict[str, Any]:
    """Build a metadata-only snapshot contract for later TEST execution."""
    contract: dict[str, Any] = {
        "snapshot_contract_version": "data-snapshot-contract-v1",
        "universe_version": candidate["universe_version"],
        "feature_schema_version": str(candidate["feature_schema_version"]),
        "target_schema_version": candidate["target_schema_version"],
        "market_data_snapshot": {
            "identifier": f"configured-tiingo-eod-through-{nominal_date_cutoff}",
            "provider": "tiingo_eod",
            "identity_basis": "configuration_metadata_and_file_hashes_only",
            "dataset_rows_inspected": False,
        },
        "nominal_date_cutoff": nominal_date_cutoff,
        "relevant_config_hashes": dict(sorted(config_hashes.items())),
        "candidate_fingerprint": candidate["candidate_fingerprint"],
        "test_values_inspected": False,
    }
    contract["data_snapshot_fingerprint"] = data_snapshot_fingerprint(contract)
    return contract


def holdout_controls() -> dict[str, Any]:
    """Return the only two authorized diagnostic controls."""
    shared_policy = {
        "test_range": "same_as_authorized_candidate",
        "retraining_frequency": "annual",
        "training_window_policy": "expanding",
        "training_history_start": TRAINING_HISTORY_START,
        "purge_rule": PURGE_RULE,
        "purge_equality_behavior": "purge",
    }
    return {
        "ridge_100": {
            "role": "primary_linear_diagnostic_control_not_candidate",
            "task": "regression",
            "target": "target_return_20d",
            "horizon": 20,
            "model": "sklearn.linear_model.Ridge",
            "hyperparameters": {"alpha": 100.0},
            "feature_set_version": "quantitative-baseline-v1",
            "preprocessing_version": "baseline-standard-v1",
            **shared_policy,
        },
        "momentum_20d": {
            "role": "naive_ranking_diagnostic_not_candidate",
            "source_definition": "Phase 3B momentum20-ranking-20d-qbaselinev1-prepv1",
            "score": "momentum_20d",
            "direction": "higher_score_ranks_higher",
            "fit_required": False,
            "retuning_allowed": False,
            "test_range": "same_as_authorized_candidate",
        },
        "only_authorized_evaluation_identities": [
            CANDIDATE_ID, "ridge_100", "momentum_20d",
        ],
    }


def holdout_threshold_contract() -> dict[str, Any]:
    """Return thresholds and exact classification boundary semantics."""
    return {
        "thresholds": dict(THRESHOLDS),
        "absolute_classification": dict(ABSOLUTE_CLASSIFICATION_RULES),
        "relative_classification": dict(RELATIVE_CLASSIFICATION_RULES),
        "boundary_semantics": dict(BOUNDARY_SEMANTICS),
    }


def one_shot_policy() -> dict[str, Any]:
    """Describe future opening metadata without opening the holdout now."""
    return {
        "holdout_opened": False,
        "holdout_executed": False,
        "first_execution_must_persist": [
            "candidate_fingerprint", "holdout_protocol_fingerprint",
            "data_snapshot_fingerprint", "test_start", "nominal_test_end",
            "effective_test_end", "opened_at", "evaluation_id",
        ],
        "opening_timestamp_has_not_been_written": True,
        "after_first_open_only_reproduction_is_allowed": True,
        "reproduction_requires_exact_match": [
            "candidate_fingerprint", "holdout_protocol_fingerprint",
            "data_snapshot_fingerprint", "test_start", "nominal_test_end",
            "effective_test_end",
        ],
        "reproduction_is_new_statistical_evaluation": False,
    }


def protocol_fingerprint_payload(protocol: Mapping[str, Any]) -> dict[str, Any]:
    """Select all semantic protocol fields and omit provenance/timing."""
    keys = (
        "protocol_version", "authorized_candidate", "test_range",
        "evaluation_procedure", "data_snapshot_fingerprint", "controls", "metrics",
        "threshold_contract", "one_shot_policy", "excluded_evaluations",
        "interpretation_policy",
    )
    missing = [key for key in keys if key not in protocol]
    if missing:
        raise ValueError(f"holdout protocol lacks fingerprint fields: {missing}")
    return {key: protocol[key] for key in keys}


def holdout_protocol_fingerprint(protocol: Mapping[str, Any]) -> str:
    """Hash every frozen holdout-protocol semantic dimension."""
    return canonical_sha256(protocol_fingerprint_payload(protocol))


def build_holdout_protocol(
    candidate: Mapping[str, Any], snapshot: Mapping[str, Any],
) -> dict[str, Any]:
    """Build the frozen protocol without fitting or evaluating anything."""
    controls = holdout_controls()
    thresholds = holdout_threshold_contract()
    protocol: dict[str, Any] = {
        "protocol_id": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "protocol_status": PROTOCOL_STATUS,
        "authorized_candidate": {
            "candidate_id": candidate["candidate_id"],
            "candidate_status": candidate["status"],
            "candidate_fingerprint": candidate["candidate_fingerprint"],
        },
        "test_range": {
            "calendar": "XNYS",
            "nominal_test_start": NOMINAL_TEST_START,
            "nominal_test_end": snapshot["nominal_date_cutoff"],
            "nominal_test_end_source": "configured data snapshot cutoff",
            "effective_test_end_rule": (
                "latest decision_date <= nominal_test_end whose "
                "target_end_date_20d is fully observable"
            ),
            "incomplete_targets_are_evaluated": False,
        },
        "evaluation_procedure": {
            "method": "causal_annual_walk_forward",
            "retraining_frequency": "annual",
            "activation_rule": "first XNYS prediction session in each calendar year",
            "fits_per_annual_period": 1,
            "training_window_policy": "expanding",
            "training_history_start": TRAINING_HISTORY_START,
            "history_constraint": "only history available before prediction_start",
            "preprocessor_policy": "new preprocessor fitted on each purged training window",
            "within_period_policy": "model and preprocessor frozen for the annual period",
            "next_period_policy": "refit at the next annual activation",
            "single_static_2010_2021_model_for_all_test_years": False,
            "purge_rule": PURGE_RULE,
            "purge_equality_behavior": "purge",
        },
        "data_snapshot_fingerprint": snapshot["data_snapshot_fingerprint"],
        "controls": controls,
        "metrics": {
            "primary": dict(PRIMARY_METRIC),
            "secondary": SECONDARY_METRICS,
            "partial_years_must_be_flagged": True,
            "portfolio_metrics_excluded": list(EXCLUDED_PORTFOLIO_METRICS),
        },
        "threshold_contract": thresholds,
        "one_shot_policy": one_shot_policy(),
        "excluded_evaluations": [
            "rf_medium_or_wide", "xgboost", "lightgbm", "5d", "10d",
            "direct_rank", "feature_subsets", "historical_position_removed",
            "different_training_windows", "different_frequencies",
            "alternative_seeds", "ensembles", "portfolio_backtest",
        ],
        "interpretation_policy": {
            "pass": (
                "Phase 3 may close as predictive candidate successfully validated; "
                "not production-ready, profitable-portfolio evidence, or trading approval"
            ),
            "marginal": (
                "record as observed; do not modify development-candidate-v1; any further "
                "research is a new development generation"
            ),
            "fail_or_hard_fail": (
                "record failure; do not reoptimize against TEST or retry a TEST-inspired "
                "candidate; TEST is no longer clean for such changes"
            ),
            "development_comparison_is_diagnostic_only": True,
        },
        "test_used": False,
        "test_opened": False,
        "holdout_executed": False,
    }
    protocol["holdout_protocol_fingerprint"] = holdout_protocol_fingerprint(protocol)
    return protocol


def classify_absolute_holdout(
    *, mean_rank_ic: float, worst_year_ic: float, positive_years: int,
    evaluable_years: int, top10_uplift: float,
) -> str:
    """Apply the predeclared absolute result rules in their frozen precedence."""
    if evaluable_years <= 0:
        raise ValueError("evaluable_years must be positive")
    if positive_years < 0 or positive_years > evaluable_years:
        raise ValueError("positive_years must be within [0, evaluable_years]")
    positive_year_share = positive_years / evaluable_years
    if mean_rank_ic <= 0:
        return "hard_fail"
    if mean_rank_ic < MARGINAL_IC_THRESHOLD:
        return "fail"
    if top10_uplift <= 0 and mean_rank_ic < PASS_IC_THRESHOLD:
        return "fail"
    if (
        mean_rank_ic >= PASS_IC_THRESHOLD
        and worst_year_ic > WORST_YEAR_PASS_FLOOR
        and positive_year_share >= POSITIVE_YEAR_SHARE_FLOOR
        and top10_uplift > 0
    ):
        return "pass"
    return "marginal"


def classify_rf_vs_ridge(*, rf_mean_rank_ic: float, ridge_mean_rank_ic: float) -> str:
    """Classify nonlinear-vs-linear performance without changing absolute status."""
    delta = rf_mean_rank_ic - ridge_mean_rank_ic
    if (
        delta > RF_RIDGE_IC_EQUIVALENCE_TOLERANCE
        and not math.isclose(
            delta, RF_RIDGE_IC_EQUIVALENCE_TOLERANCE, rel_tol=0.0, abs_tol=1e-12,
        )
    ):
        return "rf_outperforms_ridge"
    if (
        delta < -RF_RIDGE_IC_EQUIVALENCE_TOLERANCE
        and not math.isclose(
            delta, -RF_RIDGE_IC_EQUIVALENCE_TOLERANCE, rel_tol=0.0, abs_tol=1e-12,
        )
    ):
        return "ridge_outperforms_rf"
    return "approximately_equal"


def is_exact_reproduction(
    reference: Mapping[str, Any], attempted: Mapping[str, Any],
) -> bool:
    """Allow a rerun only when every frozen identity and TEST range matches."""
    required = one_shot_policy()["reproduction_requires_exact_match"]
    return all(reference.get(key) == attempted.get(key) for key in required)


def _check(name: str, expected: Any, observed: Any) -> dict[str, Any]:
    return {
        "check": name,
        "expected": expected,
        "observed": observed,
        "passed": observed == expected,
    }


def protocol_consistency_checks(
    candidate: Mapping[str, Any], snapshot: Mapping[str, Any],
    protocol: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate readiness entirely from frozen contracts and metadata."""
    checks = [
        _check("candidate_id", CANDIDATE_ID, candidate.get("candidate_id")),
        _check("candidate_status", CANDIDATE_STATUS, candidate.get("status")),
        _check("candidate_fingerprint_authorized", AUTHORIZED_CANDIDATE_FINGERPRINT, candidate.get("candidate_fingerprint")),
        _check("candidate_fingerprint_reproducible", candidate.get("candidate_fingerprint"), candidate_fingerprint(candidate)),
        _check("candidate_task", "regression", candidate.get("task")),
        _check("candidate_target", "target_return_20d", candidate.get("target")),
        _check("candidate_horizon", 20, candidate.get("horizon")),
        _check("candidate_model_family", "random_forest", candidate.get("model_family")),
        _check("candidate_model_profile", "rf-small", candidate.get("model_profile")),
        _check("candidate_hyperparameters", EXPECTED_RF_PARAMETERS, candidate.get("hyperparameters")),
        _check("candidate_feature_count", 52, candidate.get("feature_count")),
        _check("candidate_features", list(QUANTITATIVE_BASELINE_FEATURES), candidate.get("ordered_feature_names")),
        _check("candidate_feature_hash", feature_names_hash(QUANTITATIVE_BASELINE_FEATURES), candidate.get("feature_names_hash")),
        _check("candidate_feature_set", "quantitative-baseline-v1", candidate.get("feature_set_version")),
        _check("candidate_preprocessing", "tree-preprocessing-v1", candidate.get("preprocessing_version")),
        _check("candidate_frequency", "annual", candidate.get("retraining_frequency")),
        _check("candidate_window", "expanding", candidate.get("training_window_policy")),
        _check("candidate_history_start", TRAINING_HISTORY_START, candidate.get("training_history_start")),
        _check("candidate_purge", PURGE_RULE, candidate.get("purge_rule")),
        _check("candidate_purge_equality", "purge", candidate.get("purge_equality_behavior")),
        _check("candidate_sealed_test_start", NOMINAL_TEST_START, candidate.get("sealed_test_start")),
        _check("candidate_test_used", False, candidate.get("test_used")),
        _check("candidate_test_opened", False, candidate.get("test_opened")),
        _check("candidate_final_model_fitted", False, candidate.get("final_model_fitted")),
        _check("snapshot_candidate", candidate.get("candidate_fingerprint"), snapshot.get("candidate_fingerprint")),
        _check("snapshot_fingerprint", data_snapshot_fingerprint(snapshot), snapshot.get("data_snapshot_fingerprint")),
        _check("snapshot_frozen_identity", AUTHORIZED_DATA_SNAPSHOT_FINGERPRINT, snapshot.get("data_snapshot_fingerprint")),
        _check("snapshot_rows_inspected", False, snapshot.get("test_values_inspected")),
        _check("protocol_id", PROTOCOL_ID, protocol.get("protocol_id")),
        _check("protocol_status", PROTOCOL_STATUS, protocol.get("protocol_status")),
        _check("protocol_candidate", candidate.get("candidate_fingerprint"), protocol.get("authorized_candidate", {}).get("candidate_fingerprint")),
        _check("protocol_snapshot", snapshot.get("data_snapshot_fingerprint"), protocol.get("data_snapshot_fingerprint")),
        _check("protocol_fingerprint", holdout_protocol_fingerprint(protocol), protocol.get("holdout_protocol_fingerprint")),
        _check("protocol_frozen_identity", AUTHORIZED_HOLDOUT_PROTOCOL_FINGERPRINT, protocol.get("holdout_protocol_fingerprint")),
        _check("protocol_test_start", NOMINAL_TEST_START, protocol.get("test_range", {}).get("nominal_test_start")),
        _check("protocol_annual", "annual", protocol.get("evaluation_procedure", {}).get("retraining_frequency")),
        _check("protocol_expanding", "expanding", protocol.get("evaluation_procedure", {}).get("training_window_policy")),
        _check("protocol_purge", PURGE_RULE, protocol.get("evaluation_procedure", {}).get("purge_rule")),
        _check("protocol_primary_metric", PRIMARY_METRIC, protocol.get("metrics", {}).get("primary")),
        _check("protocol_thresholds", holdout_threshold_contract(), protocol.get("threshold_contract")),
        _check("protocol_controls", holdout_controls(), protocol.get("controls")),
        _check("protocol_test_used", False, protocol.get("test_used")),
        _check("protocol_test_opened", False, protocol.get("test_opened")),
        _check("protocol_holdout_executed", False, protocol.get("holdout_executed")),
    ]
    failed = [check["check"] for check in checks if not check["passed"]]
    return {
        "checks": checks,
        "passed": not failed,
        "failed_checks": failed,
        "test_used": False,
        "test_opened": False,
        "holdout_executed": False,
    }
