"""Predictive metrics with explicit pooled and cross-sectional semantics."""
from enum import Enum

import numpy as np
import pandas as pd
from sklearn.metrics import (
    balanced_accuracy_score,
    log_loss,
    mean_absolute_error,
    mean_squared_error,
    roc_auc_score,
)

from investment_system.models.contracts import TargetTask


class MetricScope(str, Enum):
    POOLED = "pooled"
    CROSS_SECTIONAL_BY_DATE = "cross_sectional_by_date"


METRICS_BY_TASK: dict[TargetTask, tuple[str, ...]] = {
    TargetTask.REGRESSION: ("mae", "rmse", "pearson_correlation", "spearman_correlation"),
    TargetTask.CLASSIFICATION: ("log_loss", "roc_auc", "balanced_accuracy"),
    TargetTask.RANKING: ("rank_ic", "mean_ic", "std_ic", "ic_information_ratio"),
}


def metric_scopes(metric_name: str) -> tuple[MetricScope, ...]:
    """Return supported aggregation contracts without calculating the metric."""
    if metric_name in {"rank_ic", "mean_ic", "std_ic", "ic_information_ratio"}:
        return (MetricScope.CROSS_SECTIONAL_BY_DATE,)
    if metric_name == "spearman_correlation":
        return (MetricScope.POOLED, MetricScope.CROSS_SECTIONAL_BY_DATE)
    if any(metric_name in names for names in METRICS_BY_TASK.values()):
        return (MetricScope.POOLED,)
    raise ValueError(f"unknown predictive metric: {metric_name}")


def _safe_correlation(actual: pd.Series, predicted: pd.Series, method: str) -> float | None:
    valid = pd.DataFrame({"actual": actual, "predicted": predicted}).dropna()
    if len(valid) < 2 or valid["actual"].nunique() < 2 or valid["predicted"].nunique() < 2:
        return None
    value = valid["actual"].corr(valid["predicted"], method=method)
    return float(value) if pd.notna(value) and np.isfinite(value) else None


def daily_correlations(
    actual: pd.Series, predicted: pd.Series, decision_dates: pd.Series, *, method: str
) -> pd.Series:
    """Compute one correlation per date, omitting degenerate cross-sections."""
    frame = pd.DataFrame({
        "actual": np.asarray(actual, dtype=float),
        "predicted": np.asarray(predicted, dtype=float),
        "decision_date": pd.to_datetime(decision_dates).dt.date.to_numpy(),
    })
    values: dict[object, float] = {}
    for day, group in frame.groupby("decision_date", sort=True):
        correlation = _safe_correlation(group["actual"], group["predicted"], method)
        if correlation is not None:
            values[day] = correlation
    return pd.Series(values, dtype=float, name=f"daily_{method}")


def ic_summary(values: pd.Series) -> dict[str, float | int | None]:
    clean = values.dropna().astype(float)
    standard_deviation = float(clean.std(ddof=1)) if len(clean) > 1 else None
    mean = float(clean.mean()) if not clean.empty else None
    icir = (
        mean / standard_deviation
        if mean is not None and standard_deviation is not None and standard_deviation > 0
        else None
    )
    return {
        "days": int(len(clean)),
        "mean": mean,
        "median": float(clean.median()) if not clean.empty else None,
        "std": standard_deviation,
        "icir": float(icir) if icir is not None else None,
        "pct_positive": float((clean > 0).mean()) if not clean.empty else None,
    }


def top_k_diagnostics(
    actual_returns: pd.Series,
    predicted_scores: pd.Series,
    decision_dates: pd.Series,
    *,
    k: int = 10,
) -> dict[str, float | int | None]:
    frame = pd.DataFrame({
        "actual": np.asarray(actual_returns, dtype=float),
        "score": np.asarray(predicted_scores, dtype=float),
        "decision_date": pd.to_datetime(decision_dates).dt.date.to_numpy(),
    }).dropna()
    rows = []
    for _, group in frame.groupby("decision_date", sort=True):
        if len(group) < k or group["score"].nunique() < 2:
            continue
        ordered = group.sort_values("score", ascending=False, kind="mergesort")
        top_return = float(ordered.head(k)["actual"].mean())
        universe_return = float(group["actual"].mean())
        rows.append((top_return, universe_return, top_return - universe_return))
    if not rows:
        return {
            "dates": 0, "average_top10_actual_return": None,
            "average_universe_actual_return": None, "average_top10_uplift": None,
            "pct_dates_positive_uplift": None,
        }
    values = np.asarray(rows)
    return {
        "dates": int(len(values)),
        "average_top10_actual_return": float(values[:, 0].mean()),
        "average_universe_actual_return": float(values[:, 1].mean()),
        "average_top10_uplift": float(values[:, 2].mean()),
        "pct_dates_positive_uplift": float((values[:, 2] > 0).mean()),
    }


def regression_metrics(
    actual: pd.Series,
    predicted: pd.Series | np.ndarray,
    decision_dates: pd.Series,
) -> dict[str, object]:
    actual_series = pd.Series(np.asarray(actual, dtype=float))
    predicted_series = pd.Series(np.asarray(predicted, dtype=float))
    spearman = daily_correlations(actual_series, predicted_series, decision_dates, method="spearman")
    pearson = daily_correlations(actual_series, predicted_series, decision_dates, method="pearson")
    return {
        "pooled": {
            "mae": float(mean_absolute_error(actual_series, predicted_series)),
            "rmse": float(np.sqrt(mean_squared_error(actual_series, predicted_series))),
            "pearson_correlation": _safe_correlation(actual_series, predicted_series, "pearson"),
            "spearman_correlation": _safe_correlation(actual_series, predicted_series, "spearman"),
        },
        "daily_pearson": ic_summary(pearson),
        "daily_spearman": ic_summary(spearman),
        "top10": top_k_diagnostics(actual_series, predicted_series, decision_dates),
    }


def classification_metrics(
    actual: pd.Series,
    probability: pd.Series | np.ndarray,
) -> dict[str, object]:
    actual_values = np.asarray(actual, dtype=int)
    probabilities = np.asarray(probability, dtype=float)
    predicted = (probabilities >= 0.5).astype(int)
    result: dict[str, object] = {
        "rows": int(len(actual_values)),
        "positive_prevalence": float(actual_values.mean()),
        "log_loss": float(log_loss(actual_values, probabilities, labels=[0, 1])),
        "balanced_accuracy": None,
        "roc_auc": None,
        "degenerate_reason": None,
    }
    if len(np.unique(actual_values)) < 2:
        result["degenerate_reason"] = "actual target contains one class"
        return result
    result["roc_auc"] = float(roc_auc_score(actual_values, probabilities))
    result["balanced_accuracy"] = float(balanced_accuracy_score(actual_values, predicted))
    return result


def ranking_metrics(
    actual_rank: pd.Series,
    actual_return: pd.Series,
    predicted_score: pd.Series | np.ndarray,
    decision_dates: pd.Series,
) -> dict[str, object]:
    scores = pd.Series(np.asarray(predicted_score, dtype=float))
    daily = daily_correlations(actual_rank.reset_index(drop=True), scores, decision_dates, method="spearman")
    return {
        "rank_ic": ic_summary(daily),
        "top10": top_k_diagnostics(actual_return.reset_index(drop=True), scores, decision_dates),
    }


def cross_sectional_percentile_rank(scores: pd.Series, decision_dates: pd.Series) -> pd.Series:
    frame = pd.DataFrame({"score": np.asarray(scores, dtype=float), "date": list(decision_dates)})
    counts = frame.groupby("date")["score"].transform("count")
    ranks = frame.groupby("date")["score"].rank(method="average")
    return ((ranks - 1) / (counts - 1)).where(counts > 1)
