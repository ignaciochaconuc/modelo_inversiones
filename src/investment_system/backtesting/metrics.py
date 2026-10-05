import numpy as np
import pandas as pd

def cumulative_return(returns: pd.Series) -> float:
    return float((1 + returns.dropna()).prod() - 1)

def annualized_volatility(returns: pd.Series, periods: int = 252) -> float:
    return float(returns.dropna().std(ddof=1) * np.sqrt(periods))

def max_drawdown(returns: pd.Series) -> float:
    equity = (1 + returns.fillna(0)).cumprod()
    return float((equity / equity.cummax() - 1).min())
