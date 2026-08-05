# -*- coding: utf-8 -*-
"""
Version Manager Prototype

Manages version.json file to detect changes.
"""
import os
import json
import time
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime


class VersionManager:
    """
    Tracks version of a shared resource.
    Used to detect changes made by other users.
    """

    def __init__(self, shared_dir: Path, version_filename: str = "version.json"):
        self.shared_dir = Path(shared_dir)
        self.version_file = self.shared_dir / version_filename
        self._current_version = self._load_version()

    def _load_version(self) -> Dict[str, Any]:
        try:
            if self.version_file.exists():
                with open(self.version_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    # Ensure required fields exist
                    if "version" not in data:
                        data["version"] = 0
                    if "last_updated" not in data:
                        data["last_updated"] = datetime.now().isoformat()
                    return data
        except Exception:
            pass
        return {"version": 0, "last_updated": datetime.now().isoformat()}

    def get_current_version(self) -> int:
        """Get the current version number."""
        return self._current_version.get("version", 0)

    def get_last_updated(self) -> str:
        """Get the last updated timestamp."""
        return self._current_version.get("last_updated", "")

    def increment_version(self, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Increment the version and write to file.
        Returns the new version number.
        """
        new_version = self._current_version.get("version", 0) + 1
        self._current_version = {
            "version": new_version,
            "last_updated": datetime.now().isoformat(),
            "updated_by": os.environ.get("USER", "unknown"),
        }
        if metadata:
            self._current_version["metadata"] = metadata

        try:
            self.shared_dir.mkdir(parents=True, exist_ok=True)
            with open(self.version_file, "w", encoding="utf-8") as f:
                json.dump(self._current_version, f, indent=2, ensure_ascii=False)
        except Exception as e:
            print(f"[VersionManager] Increment failed: {e}")

        return new_version

    def refresh(self) -> bool:
        """
        Reload version from file.
        Returns True if version changed, False otherwise.
        """
        old_version = self._current_version.get("version", 0)
        new_data = self._load_version()
        self._current_version = new_data
        new_version = self._current_version.get("version", 0)
        return new_version != old_version

    def get_version_info(self) -> Dict[str, Any]:
        """Get complete version information."""
        return self._current_version.copy()