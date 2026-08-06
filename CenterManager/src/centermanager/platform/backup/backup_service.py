# -*- coding: utf-8 -*-
"""
BackupService - creates and restores backups of runtime data.
"""
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from centermanager.core.paths import get_paths
from centermanager.events.event_bus import EventBus
from centermanager.events.collaboration_events import BackupCreated, BackupFailed

logger = logging.getLogger(__name__)


class BackupResult:
    def __init__(self, success: bool, backup_path: Optional[Path] = None, error: Optional[str] = None):
        self.success = success
        self.backup_path = backup_path
        self.error = error


class BackupService:
    def __init__(self, event_bus: Optional[EventBus] = None):
        self._backup_root = get_paths().backup_dir / "publish"
        self._backup_root.mkdir(parents=True, exist_ok=True)
        self._event_bus = event_bus

    def create_backup(self, label: str = "pre_publish") -> BackupResult:
        """Create a full backup of runtime data (database, metadata, reports)."""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_name = f"{label}_{timestamp}"
            backup_path = self._backup_root / backup_name
            backup_path.mkdir(parents=True, exist_ok=True)

            paths = get_paths()

            # Backup database
            db_src = paths.database_dir / "center.db"
            if db_src.exists():
                shutil.copy2(db_src, backup_path / "center.db")
                logger.info(f"Backed up database: {db_src}")

            # Backup metadata
            meta_src = paths.metadata_dir
            if meta_src.exists():
                meta_dst = backup_path / "metadata"
                shutil.copytree(meta_src, meta_dst, dirs_exist_ok=True)
                logger.info(f"Backed up metadata: {meta_src}")

            # Backup reports (optional - chỉ copy danh sách, không copy toàn bộ file để tránh nặng)
            # Có thể chỉ backup metadata của reports

            # Write manifest
            manifest = {
                "label": label,
                "timestamp": timestamp,
                "created_at": datetime.now().isoformat(),
                "database": "center.db",
                "metadata": "metadata/",
                "source_runtime": str(paths.runtime_root),
            }
            with open(backup_path / "manifest.json", "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)

            if self._event_bus:
                self._event_bus.publish(BackupCreated(
                    backup_path=str(backup_path),
                    label=label,
                ))

            logger.info(f"Backup created: {backup_path}")
            return BackupResult(success=True, backup_path=backup_path)

        except Exception as e:
            logger.exception("Backup creation failed")
            if self._event_bus:
                self._event_bus.publish(BackupFailed(error=str(e)))
            return BackupResult(success=False, error=str(e))

    def restore_backup(self, backup_path: Path) -> BackupResult:
        """Restore a backup to runtime."""
        try:
            paths = get_paths()
            manifest_path = backup_path / "manifest.json"
            if not manifest_path.exists():
                return BackupResult(success=False, error="Manifest not found")

            # Restore database
            db_src = backup_path / "center.db"
            if db_src.exists():
                shutil.copy2(db_src, paths.database_dir / "center.db")
                logger.info(f"Restored database from {db_src}")

            # Restore metadata
            meta_src = backup_path / "metadata"
            if meta_src.exists():
                shutil.copytree(meta_src, paths.metadata_dir, dirs_exist_ok=True)
                logger.info(f"Restored metadata from {meta_src}")

            logger.info(f"Backup restored: {backup_path}")
            return BackupResult(success=True, backup_path=backup_path)

        except Exception as e:
            logger.exception("Backup restore failed")
            return BackupResult(success=False, error=str(e))

    def list_backups(self) -> list:
        """List all available backups."""
        backups = []
        for item in self._backup_root.iterdir():
            if item.is_dir() and (item / "manifest.json").exists():
                try:
                    with open(item / "manifest.json", "r", encoding="utf-8") as f:
                        manifest = json.load(f)
                    backups.append({
                        "path": str(item),
                        "timestamp": manifest.get("timestamp"),
                        "label": manifest.get("label"),
                        "created_at": manifest.get("created_at"),
                    })
                except Exception:
                    backups.append({
                        "path": str(item),
                        "timestamp": item.name.split("_")[1] if "_" in item.name else "",
                        "label": item.name,
                    })
        return sorted(backups, key=lambda x: x.get("timestamp", ""), reverse=True)