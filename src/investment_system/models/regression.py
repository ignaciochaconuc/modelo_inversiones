from investment_system.models.base import BasePredictiveModel
class RegressionModel(BasePredictiveModel):
    """Contract for linear, LightGBM, XGBoost, or random-forest regressors."""
