import json
from pathlib import Path
from typing import Dict, Any
from .lock_repository import LockRepository

class JsonLockRepository(LockRepository):
    def __init__(self, lock_file: Path):
        self._lock_file = lock_file

    def get_lock(self) -> Dict[str, Any]:
        if not self._lock_file.exists():
            return {"locked": False, "owner": None, "session_id": None, "started_at": None}
        with open(self._lock_file, 'r', encoding='utf-8') as f:
            return json.load(f)

    def save_lock(self, data: Dict[str, Any]) -> None:
        self._lock_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self._lock_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)