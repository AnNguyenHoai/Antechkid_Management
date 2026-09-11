# -*- coding: utf-8 -*-
"""Backup and recovery service with integrity and path-boundary protection."""
import hashlib, json, logging, os, shutil, sqlite3, uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from centermanager.core.paths import get_paths
from centermanager.events.event_bus import EventBus
from centermanager.events.collaboration_events import BackupCreated, BackupFailed

logger = logging.getLogger(__name__)

class BackupResult:
    def __init__(self, success: bool, backup_path: Optional[Path] = None, error: Optional[str] = None):
        self.success, self.backup_path, self.error = success, backup_path, error

class BackupService:
    FORMAT_VERSION = 2

    def __init__(self, event_bus: Optional[EventBus] = None):
        self._backup_root = (get_paths().backup_dir / "publish").resolve()
        self._backup_root.mkdir(parents=True, exist_ok=True)
        self._event_bus = event_bus

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _is_owned_backup(self, backup_path: Path) -> bool:
        try:
            backup_path.resolve().relative_to(self._backup_root)
            return True
        except ValueError:
            return False

    def _validate_sqlite(self, db_path: Path) -> Optional[str]:
        if not db_path.is_file() or db_path.stat().st_size == 0:
            return "Database backup is missing or empty"
        try:
            con = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                row = con.execute("PRAGMA integrity_check").fetchone()
            finally:
                con.close()
            if not row or row[0] != "ok":
                return f"SQLite integrity check failed: {row[0] if row else 'unknown'}"
        except sqlite3.Error as exc:
            return f"Invalid SQLite database: {exc}"
        return None

    def _validate_backup(self, backup_path: Path) -> tuple[bool, str]:
        if not self._is_owned_backup(backup_path):
            return False, "Backup path is outside the managed backup directory"
        manifest_path = backup_path / "manifest.json"
        if not manifest_path.is_file():
            return False, "Manifest not found"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:
            return False, f"Invalid manifest: {exc}"
        if manifest.get("format_version", 1) > self.FORMAT_VERSION:
            return False, "Backup format is newer than this application supports"
        db_path = backup_path / manifest.get("database", "center.db")
        error = self._validate_sqlite(db_path)
        if error:
            return False, error
        checksum = manifest.get("checksums", {}).get(db_path.name)
        if checksum and checksum != self._sha256(db_path):
            return False, "Database checksum mismatch"
        metadata_name = manifest.get("metadata", "metadata")
        metadata = backup_path / metadata_name
        if not metadata.is_dir():
            return False, "Metadata backup is missing"
        return True, ""

    def create_backup(self, label: str = "pre_publish") -> BackupResult:
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self._backup_root / f"{label}_{timestamp}_{uuid.uuid4().hex[:8]}"
            backup_path.mkdir(parents=True)
            paths = get_paths()
            db_src = paths.database_dir / "center.db"
            if not db_src.is_file():
                raise FileNotFoundError(f"Runtime database not found: {db_src}")
            db_dst = backup_path / "center.db"
            shutil.copy2(db_src, db_dst)
            error = self._validate_sqlite(db_dst)
            if error:
                raise RuntimeError(error)
            meta_src = paths.metadata_dir
            if not meta_src.is_dir():
                raise FileNotFoundError(f"Runtime metadata not found: {meta_src}")
            shutil.copytree(meta_src, backup_path / "metadata")
            manifest = {
                "format_version": self.FORMAT_VERSION, "label": label, "timestamp": timestamp,
                "created_at": datetime.now().isoformat(), "database": "center.db", "metadata": "metadata",
                "checksums": {"center.db": self._sha256(db_dst)},
            }
            (backup_path / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            if self._event_bus:
                self._event_bus.publish(BackupCreated(backup_path=str(backup_path), label=label))
            logger.info("Backup created: %s", backup_path)
            return BackupResult(True, backup_path)
        except Exception as exc:
            logger.exception("Backup creation failed")
            if self._event_bus:
                self._event_bus.publish(BackupFailed(error=str(exc)))
            return BackupResult(False, error=str(exc))

    def restore_backup(self, backup_path: Path) -> BackupResult:
        try:
            backup_path = Path(backup_path).resolve()
            ok, error = self._validate_backup(backup_path)
            if not ok:
                return BackupResult(False, error=error)
            paths = get_paths()
            manifest = json.loads((backup_path / "manifest.json").read_text(encoding="utf-8"))
            db_src = backup_path / manifest["database"]
            meta_src = backup_path / manifest["metadata"]
            paths.database_dir.mkdir(parents=True, exist_ok=True)
            paths.metadata_dir.parent.mkdir(parents=True, exist_ok=True)
            # Atomic-ish replace: copy to temporary sibling first, then replace.
            db_tmp = paths.database_dir / f".center.db.restore-{uuid.uuid4().hex}.tmp"
            shutil.copy2(db_src, db_tmp)
            db_error = self._validate_sqlite(db_tmp)
            if db_error:
                db_tmp.unlink(missing_ok=True)
                return BackupResult(False, error=db_error)
            os.replace(db_tmp, paths.database_dir / "center.db")
            meta_target = paths.metadata_dir
            meta_tmp = meta_target.parent / f".metadata.restore-{uuid.uuid4().hex}"
            shutil.copytree(meta_src, meta_tmp)
            old_meta = meta_target.parent / f".metadata.previous-{uuid.uuid4().hex}"
            if meta_target.exists():
                os.replace(meta_target, old_meta)
            try:
                os.replace(meta_tmp, meta_target)
            except Exception:
                if old_meta.exists():
                    os.replace(old_meta, meta_target)
                raise
            if old_meta.exists():
                shutil.rmtree(old_meta)
            logger.info("Backup restored: %s", backup_path)
            return BackupResult(True, backup_path)
        except Exception as exc:
            logger.exception("Backup restore failed")
            return BackupResult(False, error=str(exc))

    def list_backups(self) -> list:
        backups = []
        for item in self._backup_root.iterdir():
            if not item.is_dir() or not (item / "manifest.json").is_file():
                continue
            try:
                manifest = json.loads((item / "manifest.json").read_text(encoding="utf-8"))
                valid, error = self._validate_backup(item)
                backups.append({"path": str(item), "timestamp": manifest.get("timestamp"), "label": manifest.get("label"),
                                "created_at": manifest.get("created_at"), "status": "valid" if valid else "invalid",
                                "error": error if not valid else None})
            except Exception as exc:
                backups.append({"path": str(item), "timestamp": "", "label": item.name, "status": "invalid", "error": str(exc)})
        return sorted(backups, key=lambda x: x.get("timestamp") or "", reverse=True)
