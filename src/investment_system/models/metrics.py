"""Metric names and aggregation semantics for future predictive evaluation."""
from enum import Enum

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
