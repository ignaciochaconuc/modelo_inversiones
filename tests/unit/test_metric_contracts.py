import pytest

from investment_system.models.contracts import TargetTask
from investment_system.models.metrics import METRICS_BY_TASK, MetricScope, metric_scopes


def test_metric_contracts_cover_tasks_and_aggregation_semantics() -> None:
    assert {"mae", "rmse", "pearson_correlation", "spearman_correlation"} <= set(
        METRICS_BY_TASK[TargetTask.REGRESSION]
    )
    assert {"log_loss", "roc_auc", "balanced_accuracy"} <= set(
        METRICS_BY_TASK[TargetTask.CLASSIFICATION]
    )
    assert MetricScope.CROSS_SECTIONAL_BY_DATE in metric_scopes("spearman_correlation")
    assert metric_scopes("rank_ic") == (MetricScope.CROSS_SECTIONAL_BY_DATE,)
    assert metric_scopes("mae") == (MetricScope.POOLED,)
    with pytest.raises(ValueError, match="unknown"):
        metric_scopes("accuracy")
