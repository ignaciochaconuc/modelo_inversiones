from investment_system.core.config import load_news_settings, load_settings
from investment_system.data.storage.news_store import NewsStore
from investment_system.data.validation.validators import validate_feature_target_separation

if __name__ == "__main__":
    validate_feature_target_separation()
    print("Feature and target columns are disjoint.")
    settings = load_settings()
    news_settings = load_news_settings()
    news_store = NewsStore(
        settings.paths.raw, settings.paths.processed,
        schema_version=news_settings.schema_version,
        normalizer_version=news_settings.normalizer_version,
    )
    integrity = news_store.validate_integrity()
    failures = {name: integrity[name] for name in ("bad_raw_hashes", "missing_lineage", "duplicate_records") if integrity[name]}
    if failures:
        raise ValueError(f"News Store integrity failed: {failures}")
    print(f"News Store integrity passed: {integrity}")
