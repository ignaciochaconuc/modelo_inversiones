from investment_system.data.schemas.features import FEATURE_COLUMNS, TARGET_COLUMNS

def feature_columns() -> tuple[str, ...]:
    return tuple(FEATURE_COLUMNS)

def target_columns() -> tuple[str, ...]:
    return tuple(TARGET_COLUMNS)
