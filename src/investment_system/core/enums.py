from enum import StrEnum

class AssetClass(StrEnum):
    US_EQUITY = "US_EQUITY"
    CRYPTO = "CRYPTO"

class EarningsMode(StrEnum):
    PRE_EARNINGS = "PRE_EARNINGS"
    POST_EARNINGS = "POST_EARNINGS"

class RiskAction(StrEnum):
    APPROVE = "APPROVE"
    REDUCE = "REDUCE"
    BLOCK = "BLOCK"

class TaskComplexity(StrEnum):
    SIMPLE = "simple"
    STANDARD = "standard"
    COMPLEX = "complex"
