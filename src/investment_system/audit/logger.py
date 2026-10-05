import json
from pathlib import Path
from investment_system.audit.schemas import DecisionAuditRecord

class AuditLogger:
    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
    def append(self, record: DecisionAuditRecord) -> None:
        with self.path.open("a", encoding="utf-8") as stream:
            stream.write(record.model_dump_json() + "\n")
    def read_all(self) -> list[DecisionAuditRecord]:
        if not self.path.exists(): return []
        return [DecisionAuditRecord.model_validate(json.loads(line)) for line in self.path.read_text(encoding="utf-8").splitlines() if line]
