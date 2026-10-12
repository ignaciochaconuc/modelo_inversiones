"""Immutable local attempt records with explicit TTL; cache is only an index."""
from datetime import datetime, timezone
import json
from pathlib import Path
import re
from pydantic import TypeAdapter

from investment_system.core.time_utils import ensure_utc
from investment_system.data.storage.news_store import NewsStore
from investment_system.llm.cache import AnalysisCache
from investment_system.agents.news_interpretation.runtime_schemas import StoredInterpretationAttempt, StoredInterpretationAttemptV2

ATTEMPT_ADAPTER = TypeAdapter(StoredInterpretationAttempt | StoredInterpretationAttemptV2)


LOCAL_ROOT=Path("data/cache/news_interpretation")


class LocalInterpretationStore:
    def __init__(self,root: str | Path=LOCAL_ROOT,*,allowed_root: str | Path=LOCAL_ROOT):
        self.root=Path(root).resolve()
        if not self.root.is_relative_to(Path(allowed_root).resolve()):
            raise ValueError("content storage must remain in the restricted local tree")
        self.cache=AnalysisCache(self.root/"index")

    def record_path(self,record_id: str) -> Path:
        if not re.fullmatch(r"[a-f0-9]{64}",record_id):
            raise ValueError("invalid record identity")
        return self.root/"attempts"/(record_id+".json")

    def write(self,record: StoredInterpretationAttempt) -> str:
        record=ATTEMPT_ADAPTER.validate_python(record.model_dump(mode="json"))
        path=self.record_path(record.record_id)
        if path.exists():
            if json.loads(path.read_text(encoding="utf-8")) != record.model_dump(mode="json"):
                raise ValueError("immutable record collision")
        else:
            NewsStore._atomic_json(path,record.model_dump(mode="json"))
        return record.record_id

    def read(self,record_id: str,*,now: datetime | None=None) -> StoredInterpretationAttempt:
        record=ATTEMPT_ADAPTER.validate_json(self.record_path(record_id).read_text(encoding="utf-8"))
        if record.record_id != record_id:
            raise ValueError("stored record hash mismatch")
        if ensure_utc(now or datetime.now(timezone.utc)) >= record.expires_at:
            raise ValueError("restricted content retention expired; do not replay")
        return record

    def cache_get(self,key: str,*,now: datetime) -> StoredInterpretationAttempt | None:
        pointer=self.cache.get(key,key,"news-inference-cache-v1")
        if pointer is None:
            return None
        record=self.read(pointer["analysis"]["record_id"],now=now)
        if record.cache_key != key or record.outcome not in {"interpreted","abstained"}:
            raise ValueError("unauthorized cache entry")
        return record

    def cache_put(self,record: StoredInterpretationAttempt) -> None:
        self.cache.put(record.cache_key,record.cache_key,record.requested_model,"news-inference-cache-v1",{"record_id":record.record_id})
