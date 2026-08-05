from pathlib import Path
import json
from typing import Optional
from .metadata_repository import MetadataRepository

class MetadataInitializer:
    def __init__(self, repository: MetadataRepository):
        self._repository = repository

    def ensure_initialized(self) -> None:
        # Lock
        lock = self._repository.load_lock()
        if not lock:
            self._repository.save_lock({
                "locked": False,
                "owner": None,
                "session_id": None,
                "started_at": None
            })

        # Version
        version = self._repository.load_version()
        if not version:
            self._repository.save_version({"platform_version": 1})

        # Deployment
        deployment = self._repository.load_deployment()
        if not deployment:
            self._repository.save_deployment({"profile": "Standalone"})