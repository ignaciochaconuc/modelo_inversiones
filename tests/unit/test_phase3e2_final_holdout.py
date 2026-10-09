from copy import deepcopy
from datetime import date, datetime, timedelta, timezone
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from investment_system.data.calendar import XNYSTradingCalendar
from investment_system.models.feature_sets import QUANTITATIVE_BASELINE_FEATURES
from investment_system.models.final_holdout import (
    EVALUATION_ID,
    build_holdout_frame,
    evaluate_predictions,
    open_before_load,
    persist_opening_record,
    preflight_checks,
    run_annual_model,
)


def _contracts() -> tuple[dict, dict, dict, dict]:
    root = Path("data/reports/models/phase3e/protocol")
    return (
        json.loads(Path("data/reports/models/phase3d/final_candidate/candidate_contract.json").read_text()),
        json.loads((root / "holdout_protocol.json").read_text()),
        json.loads((root / "snapshot_contract.json").read_text()),
        json.loads((root / "phase3e1_summary.json").read_text()),
    )


def _feature_values(ticker_index: int, date_index: int) -> dict[str, float]:
    return {
        name: (
            1000.0 + ticker_index if name.startswith("avg_dollar_volume")
            else ticker_index / 100 + date_index / 1000 + feature_index / 10000
        )
        for feature_index, name in enumerate(QUANTITATIVE_BASELINE_FEATURES)
    }


def _frame() -> pd.DataFrame:
    dates_and_ends = (
        (date(2010, 1, 4), date(2010, 2, 2)),
        (date(2021, 12, 1), date(2022, 1, 3)),  # equality must be purged for 2022
        (date(2022, 1, 3), date(2022, 2, 1)),
        (date(2022, 12, 1), date(2022, 12, 30)),
        (date(2023, 1, 3), date(2023, 2, 1)),
        (date(2023, 6, 1), date(2023, 6, 30)),
    )
    rows = []
    for date_index, (decision_date, target_end) in enumerate(dates_and_ends):
        for ticker_index in range(30):
            rows.append({
                "ticker": f"T{ticker_index:02d}", "decision_date": decision_date,
                "target_return_20d": ticker_index / 1000 + date_index / 10000,
                "target_rank_20d": ticker_index / 29,
                "target_end_date_20d": target_end,
                **_feature_values(ticker_index, date_index),
            })
    return pd.DataFrame(rows)


def test_preflight_failure_does_not_create_opening_record(tmp_path) -> None:
    candidate, protocol, snapshot, summary = _contracts()
    changed = deepcopy(protocol)
    changed["holdout_protocol_fingerprint"] = "0" * 64
    result = preflight_checks(candidate, changed, snapshot, summary)
    assert result["passed"] is False
    assert not (tmp_path / "opening_record.json").exists()


def test_opening_record_is_atomic_precedes_load_and_cannot_revert(tmp_path) -> None:
    candidate, protocol, snapshot, _ = _contracts()
    path = tmp_path / "opening_record.json"
    observed = []

    def loader() -> tuple[pd.DataFrame, pd.DataFrame]:
        observed.append(json.loads(path.read_text())["test_opened"])
        return pd.DataFrame(), pd.DataFrame()

    instant = datetime(2026, 10, 9, 12, 0, tzinfo=timezone.utc)
    record, execution_type, _, _ = open_before_load(
        path, candidate, protocol, snapshot, loader, now=lambda: instant,
    )
    assert observed == [True]
    assert record["evaluation_id"] == EVALUATION_ID
    assert execution_type == "first_official_evaluation"
    original = path.read_bytes()
    resumed, execution_type = persist_opening_record(
        path, candidate, protocol, snapshot,
        now=lambda: instant + timedelta(days=1),
    )
    assert execution_type == "reproduction_or_resume"
    assert resumed["opened_at"] == instant.isoformat()
    assert path.read_bytes() == original
    changed = deepcopy(protocol)
    changed["holdout_protocol_fingerprint"] = "f" * 64
    with pytest.raises(ValueError, match="identity mismatch"):
        persist_opening_record(path, candidate, changed, snapshot)
    assert path.read_bytes() == original


def test_walkforward_is_annual_expanding_strict_and_allows_prior_test_labels() -> None:
    frame = _frame()
    calendar = XNYSTradingCalendar()
    predictions, fits, preprocessing = run_annual_model(
        frame, "ridge_100", calendar,
        test_start=date(2022, 1, 3), effective_end=date(2023, 6, 1),
    )
    assert len(fits) == 2
    assert fits["preprocessing_version"].eq("baseline-standard-v1").all()
    assert fits["hyperparameters"].eq('{"alpha": 100.0}').all()
    assert (pd.to_datetime(fits["max_train_target_end_date"]).dt.date < fits["prediction_start"]).all()
    assert fits.loc[fits["prediction_year"].eq(2022), "purged_rows"].iloc[0] == 30
    assert fits.loc[fits["prediction_year"].eq(2023), "previous_test_year_training_rows"].iloc[0] == 60
    assert predictions["decision_date"].min() == date(2022, 1, 3)
    assert predictions["decision_date"].max() == date(2023, 6, 1)
    assert predictions["test_used"].all()
    assert preprocessing.groupby("fit_id").size().eq(52).all()


def test_candidate_identity_is_exact_rf_small() -> None:
    predictions, fits, preprocessing = run_annual_model(
        _frame(), "development-candidate-v1", XNYSTradingCalendar(),
        test_start=date(2022, 1, 3), effective_end=date(2022, 12, 1),
    )
    assert len(fits) == 1
    assert json.loads(fits.iloc[0]["hyperparameters"]) == {
        "n_estimators": 300, "max_depth": 4, "min_samples_leaf": 100,
        "max_features": "sqrt", "bootstrap": True, "random_state": 42,
        "n_jobs": -1,
    }
    assert fits.iloc[0]["preprocessing_version"] == "tree-preprocessing-v1"
    assert predictions["model_identity"].eq("development-candidate-v1").all()
    assert preprocessing.groupby("fit_id").size().eq(52).all()


def test_effective_end_excludes_incomplete_20d_tail() -> None:
    decision_dates = [date(2026, 9, 1), date(2026, 9, 2), date(2026, 10, 5)]
    target_ends = [date(2026, 9, 30), date(2026, 10, 6), date(2026, 11, 3)]
    feature_rows, target_rows = [], []
    for date_index, (decision_date, target_end) in enumerate(zip(decision_dates, target_ends)):
        for ticker_index in range(20):
            feature_rows.append({
                "ticker": f"T{ticker_index:02d}", "decision_date": decision_date,
                "model_eligible": True, "feature_corporate_action_contaminated": False,
                **_feature_values(ticker_index, date_index),
            })
            target_rows.append({
                "ticker": f"T{ticker_index:02d}", "decision_date": decision_date,
                "target_return_20d": ticker_index / 1000 if target_end <= date(2026, 10, 5) else np.nan,
                "target_rank_20d": ticker_index / 19 if target_end <= date(2026, 10, 5) else np.nan,
                "target_end_date_20d": target_end,
                "target_20d_training_eligible": target_end <= date(2026, 10, 5),
            })
    frame, diagnostics = build_holdout_frame(pd.DataFrame(feature_rows), pd.DataFrame(target_rows))
    assert diagnostics["effective_test_end"] == "2026-09-01"
    assert diagnostics["excluded_incomplete_tail_decision_dates"] == ["2026-09-02", "2026-10-05"]
    assert diagnostics["excluded_incomplete_tail_session_count"] == 2
    assert diagnostics["excluded_incomplete_tail_row_count"] == 40
    assert frame["decision_date"].max() == date(2026, 9, 1)


def test_metrics_known_ic_top10_partial_year_and_reproduction() -> None:
    rows = []
    for decision_date in (date(2025, 12, 31), date(2026, 6, 1)):
        for index in range(20):
            rows.append({
                "model_identity": "development-candidate-v1", "ticker": f"T{index:02d}",
                "decision_date": decision_date, "actual_return_20d": index / 100,
                "actual_rank_20d": index / 19, "predicted_return": index / 100,
                "score": index / 100, "fit_id": "fit", "year": decision_date.year,
                "test_used": True, "predicted_rank": index / 19,
            })
    predictions = pd.DataFrame(rows)
    first = evaluate_predictions(
        predictions, XNYSTradingCalendar(), date(2026, 6, 1),
    )
    second = evaluate_predictions(
        predictions.copy(), XNYSTradingCalendar(), date(2026, 6, 1),
    )
    assert first == second
    assert first["ranking"]["rank_ic"]["mean"] == pytest.approx(1.0)
    assert first["ranking"]["top10"]["average_top10_uplift"] > 0
    assert first["annual"]["2025"]["partial_year"] is False
    assert first["annual"]["2026"]["partial_year"] is True
