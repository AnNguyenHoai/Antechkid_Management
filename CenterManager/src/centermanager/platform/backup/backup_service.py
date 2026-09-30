# -*- coding: utf-8 -*-
"""Backup and recovery service with encrypted production snapshots.

Production backups use the same SQLCipher workspace key as the runtime database.
No plaintext database or plaintext restore temporary file is created while the
encrypted production boundary is active.
"""
import hashlib
import json
import logging
import os
import shutil
import sqlite3
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

from centermanager.core.paths import get_paths
from centermanager.events.event_bus import EventBus
from centermanager.events.collaboration_events import BackupCreated, BackupFailed
from centermanager.database.session import quiesce_runtime_db, refresh_runtime_db
from centermanager.database.encryption import (
    DatabaseEncryptionError,
    DatabaseKeyStore,
    apply_sqlcipher_key,
    database_encryption_required,
    is_plaintext_sqlite_file,
    load_sqlcipher_driver,
)
from centermanager.platform.backup.restore_authorization import (
    validate_restore_authorization,
)

logger = logging.getLogger(__name__)


class BackupResult:
    def __init__(self, success: bool, backup_path: Optional[Path] = None, error: Optional[str] = None):
        self.success, self.backup_path, self.error = success, backup_path, error


class BackupService:
    FORMAT_VERSION = 3

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

    @staticmethod
    def _fsync_file(path: Path) -> None:
        with path.open("r+b") as handle:
            handle.flush()
            os.fsync(handle.fileno())

    @staticmethod
    def _copy_plain_sqlite_snapshot(source_path: Path, destination_path: Path) -> None:
        """Create a transactionally consistent plaintext SQLite snapshot."""
        source_uri = source_path.resolve().as_uri() + "?mode=ro"
        source = sqlite3.connect(source_uri, uri=True)
        destination = sqlite3.connect(destination_path)
        try:
            source.backup(destination)
        finally:
            destination.close()
            source.close()

    @staticmethod
    def _copy_sqlite_snapshot(source_path: Path, destination_path: Path) -> None:
        """Backward-compatible plaintext snapshot helper for non-production callers.

        Production backup creation never calls this compatibility alias when the
        encryption policy is active; it routes through the keyed SQLCipher helper.
        """
        BackupService._copy_plain_sqlite_snapshot(source_path, destination_path)

    @staticmethod
    def _copy_encrypted_sqlite_snapshot(source_path: Path, destination_path: Path, key: bytes) -> None:
        """Create a logical SQLCipher snapshot into a keyed destination.

        Both connections are keyed before schema/page access. SQLite's online
        backup API therefore captures committed WAL contents while the
        destination pager writes ciphertext with the workspace key.
        """
        sqlcipher = load_sqlcipher_driver()
        source_uri = source_path.resolve().as_uri() + "?mode=ro"
        source = sqlcipher.connect(source_uri, uri=True)
        destination = sqlcipher.connect(str(destination_path))
        try:
            apply_sqlcipher_key(source, key)
            source.execute("SELECT count(*) FROM sqlite_master").fetchone()
            apply_sqlcipher_key(destination, key)
            source.backup(destination)
            destination.commit()
        finally:
            destination.close()
            source.close()

    @staticmethod
    def _validate_plain_sqlite(db_path: Path) -> Optional[str]:
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

    @staticmethod
    def _validate_encrypted_sqlite(db_path: Path, key: bytes) -> Optional[str]:
        if not db_path.is_file() or db_path.stat().st_size == 0:
            return "Database backup is missing or empty"
        if is_plaintext_sqlite_file(db_path):
            return "Plaintext SQLite database is forbidden by the production encryption policy"
        try:
            sqlcipher = load_sqlcipher_driver()
            con = sqlcipher.connect(db_path.resolve().as_uri() + "?mode=ro", uri=True)
            try:
                apply_sqlcipher_key(con, key)
                con.execute("SELECT count(*) FROM sqlite_master").fetchone()
                row = con.execute("PRAGMA integrity_check").fetchone()
            finally:
                con.close()
            if not row or row[0] != "ok":
                return f"SQLCipher integrity check failed: {row[0] if row else 'unknown'}"
        except Exception as exc:
            return f"Invalid encrypted database or wrong workspace key: {exc}"
        return None

    def _encryption_context(self) -> tuple[bool, Optional[bytes]]:
        encrypted = database_encryption_required()
        if not encrypted:
            return False, None
        return True, DatabaseKeyStore().load()

    def _validate_database(self, db_path: Path, *, encrypted: bool, key: Optional[bytes]) -> Optional[str]:
        if encrypted:
            if key is None:
                return "Production database key is unavailable"
            return self._validate_encrypted_sqlite(db_path, key)
        return self._validate_plain_sqlite(db_path)

    def _is_owned_backup(self, backup_path: Path) -> bool:
        try:
            backup_path.resolve().relative_to(self._backup_root)
            return True
        except ValueError:
            return False

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

        try:
            encryption_required, key = self._encryption_context()
        except DatabaseEncryptionError as exc:
            return False, str(exc)

        backup_encrypted = bool(manifest.get("database_encrypted", False))
        if encryption_required and not backup_encrypted:
            return False, "Plaintext/legacy backup is forbidden by the production encryption policy"

        db_path = backup_path / manifest.get("database", "center.db")
        error = self._validate_database(
            db_path,
            encrypted=backup_encrypted,
            key=key if backup_encrypted else None,
        )
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
        backup_path: Optional[Path] = None
        try:
            encrypted, key = self._encryption_context()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self._backup_root / f"{label}_{timestamp}_{uuid.uuid4().hex[:8]}"
            backup_path.mkdir(parents=True)
            paths = get_paths()
            db_src = paths.database_dir / "center.db"
            if not db_src.is_file():
                raise FileNotFoundError(f"Runtime database not found: {db_src}")

            source_error = self._validate_database(db_src, encrypted=encrypted, key=key)
            if source_error:
                raise RuntimeError(source_error)

            db_dst = backup_path / "center.db"
            if encrypted:
                assert key is not None
                self._copy_encrypted_sqlite_snapshot(db_src, db_dst, key)
            else:
                self._copy_plain_sqlite_snapshot(db_src, db_dst)
            self._fsync_file(db_dst)

            error = self._validate_database(db_dst, encrypted=encrypted, key=key)
            if error:
                raise RuntimeError(error)

            meta_src = paths.metadata_dir
            if not meta_src.is_dir():
                raise FileNotFoundError(f"Runtime metadata not found: {meta_src}")
            shutil.copytree(meta_src, backup_path / "metadata")
            manifest = {
                "format_version": self.FORMAT_VERSION,
                "label": label,
                "timestamp": timestamp,
                "created_at": datetime.now().isoformat(),
                "database": "center.db",
                "database_encrypted": encrypted,
                "encryption": "sqlcipher-workspace-key-v1" if encrypted else "none",
                "metadata": "metadata",
                "checksums": {"center.db": self._sha256(db_dst)},
            }
            manifest_path = backup_path / "manifest.json"
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
            self._fsync_file(manifest_path)
            if self._event_bus:
                self._event_bus.publish(BackupCreated(backup_path=str(backup_path), label=label))
            logger.info("Backup created: %s (encrypted=%s)", backup_path, encrypted)
            return BackupResult(True, backup_path)
        except Exception as exc:
            logger.exception("Backup creation failed")
            if backup_path is not None and backup_path.exists():
                shutil.rmtree(backup_path, ignore_errors=True)
            if self._event_bus:
                self._event_bus.publish(BackupFailed(error=str(exc)))
            return BackupResult(False, error=str(exc))

    def restore_backup(self, backup_path: Path, *, authorization=None) -> BackupResult:
        # Fail closed before validation/staging so a direct platform-layer call
        # cannot bypass the application destructive-operation contract.
        try:
            validate_restore_authorization(authorization)
        except Exception as exc:
            return BackupResult(False, error=str(exc))

        db_tmp: Optional[Path] = None
        meta_tmp: Optional[Path] = None
        old_db: Optional[Path] = None
        old_meta: Optional[Path] = None
        preserved_sidecars: list[tuple[Path, Path]] = []
        runtime_db: Optional[Path] = None
        meta_target: Optional[Path] = None
        db_installed = False
        meta_installed = False
        db_preserved = False
        meta_preserved = False

        try:
            backup_path = Path(backup_path).resolve()
            ok, error = self._validate_backup(backup_path)
            if not ok:
                return BackupResult(False, error=error)

            encrypted, key = self._encryption_context()
            paths = get_paths()
            manifest = json.loads((backup_path / "manifest.json").read_text(encoding="utf-8"))
            backup_encrypted = bool(manifest.get("database_encrypted", False))
            db_src = backup_path / manifest["database"]
            meta_src = backup_path / manifest["metadata"]
            paths.database_dir.mkdir(parents=True, exist_ok=True)
            paths.metadata_dir.parent.mkdir(parents=True, exist_ok=True)

            # Stage and validate both halves before touching live runtime state.
            db_tmp = paths.database_dir / f".center.db.restore-{uuid.uuid4().hex}.tmp"
            shutil.copy2(db_src, db_tmp)
            self._fsync_file(db_tmp)
            db_error = self._validate_database(
                db_tmp,
                encrypted=backup_encrypted,
                key=key if backup_encrypted else None,
            )
            if db_error:
                db_tmp.unlink(missing_ok=True)
                db_tmp = None
                return BackupResult(False, error=db_error)

            meta_target = paths.metadata_dir
            meta_tmp = meta_target.parent / f".metadata.restore-{uuid.uuid4().hex}"
            shutil.copytree(meta_src, meta_tmp)

            runtime_db = paths.database_dir / "center.db"
            old_db = paths.database_dir / f".center.db.previous-{uuid.uuid4().hex}"
            old_meta = meta_target.parent / f".metadata.previous-{uuid.uuid4().hex}"

            # All validation/staging above is non-destructive. Before the first
            # live rename, release process-owned SQLAlchemy/SQLite handles. This
            # is required on Windows where an open center.db cannot be renamed.
            quiesce_runtime_db()

            # All live mutations, including preservation, participate in one
            # rollback boundary. A failure while moving WAL/SHM, the runtime DB,
            # or live metadata must restore everything already moved.
            try:
                for suffix in ("-wal", "-shm"):
                    sidecar = Path(str(runtime_db) + suffix)
                    if sidecar.exists():
                        preserved = paths.database_dir / (
                            f".{sidecar.name}.previous-{uuid.uuid4().hex}"
                        )
                        os.replace(sidecar, preserved)
                        preserved_sidecars.append((sidecar, preserved))

                if runtime_db.exists():
                    os.replace(runtime_db, old_db)
                    db_preserved = True
                if meta_target.exists():
                    os.replace(meta_target, old_meta)
                    meta_preserved = True

                os.replace(db_tmp, runtime_db)
                db_tmp = None
                db_installed = True

                os.replace(meta_tmp, meta_target)
                meta_tmp = None
                meta_installed = True

                final_error = self._validate_database(
                    runtime_db,
                    encrypted=encrypted,
                    key=key,
                )
                if final_error:
                    raise RuntimeError(
                        f"Restored runtime database failed validation: {final_error}"
                    )

                # Keep previous runtime artifacts until the process-level DB
                # refresh also succeeds; refresh failure therefore remains
                # rollback-safe rather than reporting a failed partial restore.
                refresh_runtime_db()
            except Exception:
                if db_installed and runtime_db.exists():
                    runtime_db.unlink(missing_ok=True)
                if meta_installed and meta_target.exists():
                    shutil.rmtree(meta_target, ignore_errors=True)

                if db_preserved and old_db is not None and old_db.exists():
                    os.replace(old_db, runtime_db)
                if meta_preserved and old_meta is not None and old_meta.exists():
                    os.replace(old_meta, meta_target)
                for live, preserved in reversed(preserved_sidecars):
                    if preserved.exists():
                        os.replace(preserved, live)
                try:
                    refresh_runtime_db()
                except Exception:
                    logger.exception("Runtime DB refresh failed after restore rollback")
                raise

            if old_db is not None and old_db.exists():
                old_db.unlink(missing_ok=True)
            if old_meta is not None and old_meta.exists():
                shutil.rmtree(old_meta, ignore_errors=True)
            for _, preserved in preserved_sidecars:
                preserved.unlink(missing_ok=True)

            logger.info("Backup restored: %s (encrypted=%s)", backup_path, encrypted)
            return BackupResult(True, backup_path)
        except Exception as exc:
            logger.exception("Backup restore failed")
            if db_tmp is not None:
                db_tmp.unlink(missing_ok=True)
            if meta_tmp is not None and meta_tmp.exists():
                shutil.rmtree(meta_tmp, ignore_errors=True)
            return BackupResult(False, error=str(exc))

    def list_backups(self) -> list:
        backups = []
        for item in self._backup_root.iterdir():
            if not item.is_dir() or not (item / "manifest.json").is_file():
                continue
            try:
                manifest = json.loads((item / "manifest.json").read_text(encoding="utf-8"))
                valid, error = self._validate_backup(item)
                backups.append({
                    "path": str(item),
                    "timestamp": manifest.get("timestamp"),
                    "label": manifest.get("label"),
                    "created_at": manifest.get("created_at"),
                    "status": "valid" if valid else "invalid",
                    "error": error if not valid else None,
                })
            except Exception as exc:
                backups.append({
                    "path": str(item),
                    "timestamp": "",
                    "label": item.name,
                    "status": "invalid",
                    "error": str(exc),
                })
        return sorted(backups, key=lambda x: x.get("timestamp") or "", reverse=True)