import json
from pathlib import Path
from typing import Dict, Any
from .metadata_repository import MetadataRepository

class JsonMetadataRepository(MetadataRepository):
    def __init__(self, metadata_dir: Path):
        self._metadata_dir = metadata_dir
        self._lock_file = metadata_dir / "lock.json"
        self._version_file = metadata_dir / "version.json"
        self._deployment_file = metadata_dir / "deployment.json"

    def load_lock(self) -> Dict[str, Any]:
        return self._load_json(self._lock_file)

    def save_lock(self, data: Dict[str, Any]) -> None:
        self._save_json(self._lock_file, data)

    def load_version(self) -> Dict[str, Any]:
        return self._load_json(self._version_file)

    def save_version(self, data: Dict[str, Any]) -> None:
        self._save_json(self._version_file, data)

    def load_deployment(self) -> Dict[str, Any]:
        return self._load_json(self._deployment_file)

    def save_deployment(self, data: Dict[str, Any]) -> None:
        self._save_json(self._deployment_file, data)

    def _load_json(self, path: Path) -> Dict[str, Any]:
        if not path.exists():
            return {}
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_json(self, path: Path, data: Dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)