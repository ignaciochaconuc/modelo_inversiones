import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

def content_hash(content: str | bytes) -> str:
    raw = content.encode("utf-8") if isinstance(content, str) else content
    return hashlib.sha256(raw).hexdigest()

class AnalysisCache:
    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
    def get(self, source_id: str, content: str | bytes, analysis_version: str) -> dict[str, Any] | None:
        path = self.root / f"{hashlib.sha256(source_id.encode()).hexdigest()}.json"
        if not path.exists(): return None
        payload = json.loads(path.read_text(encoding="utf-8"))
        if payload["content_hash"] != content_hash(content) or payload["analysis_version"] != analysis_version: return None
        return payload
    def put(self, source_id: str, content: str | bytes, model_used: str, analysis_version: str, analysis: dict[str, Any]) -> Path:
        path = self.root / f"{hashlib.sha256(source_id.encode()).hexdigest()}.json"
        payload = {"source_id": source_id, "content_hash": content_hash(content), "last_analyzed_at": datetime.now(timezone.utc).isoformat(), "model_used": model_used, "analysis_version": analysis_version, "analysis": analysis}
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path
