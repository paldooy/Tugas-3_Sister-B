import hashlib
import json
import os
import time
from typing import Any, Dict


class AuditLogger:
    def __init__(self, node_id: str, data_dir: str):
        self.node_id = node_id
        self.path = os.path.join(data_dir, "audit.log")
        self.last_hash = ""
        self._load_last_hash()

    def _load_last_hash(self):
        if not os.path.exists(self.path):
            return
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                if not lines:
                    return
                last = json.loads(lines[-1])
                self.last_hash = last.get("hash", "")
        except Exception:
            self.last_hash = ""

    def log_event(self, event: Dict[str, Any]):
        record = {
            "ts": time.time(),
            "node_id": self.node_id,
            "prev_hash": self.last_hash,
            **event,
        }
        digest = hashlib.sha256(json.dumps(record, sort_keys=True).encode("utf-8")).hexdigest()
        record["hash"] = digest
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
        self.last_hash = digest
