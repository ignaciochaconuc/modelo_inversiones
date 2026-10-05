from investment_system.llm.cache import AnalysisCache, content_hash

def test_hash_is_stable_and_cache_invalidates(tmp_path) -> None:
    assert content_hash("abc") == content_hash(b"abc")
    cache = AnalysisCache(tmp_path)
    cache.put("doc-1", "content", "model", "v1", {"score": 1})
    assert cache.get("doc-1", "content", "v1")["analysis"]["score"] == 1
    assert cache.get("doc-1", "changed", "v1") is None
    assert cache.get("doc-1", "content", "v2") is None
