# -*- coding: utf-8 -*-
"""
StartupSynchronization - One-time startup sync before login.
Ensures local repository and runtime database are current.
Always prioritizes remote repository as source of truth.
"""
import logging
import shutil
from pathlib import Path
import os, json
from centermanager.core.paths import get_paths
from centermanager.platform.synchronization import GitSynchronizationProvider

logger = logging.getLogger(__name__)


class StartupSynchronization:
    """
    Performs one-time synchronization at application startup.
    Clones/pulls repository and applies database before login.
    Always resets to remote if local is ahead.
    """

    def __init__(self, provider: GitSynchronizationProvider):
        self._provider = provider
        self._paths = get_paths()
        self._repo_path = self._paths.runtime_root / "repository"
        self._runtime_db_path = self._paths.database_dir / "center.db"
        self._runtime_manifest_path = self._paths.runtime_root / "manifest.json"
        self._metadata_dir = self._paths.metadata_dir

    def run(self) -> bool:
        """Execute startup synchronization."""
        logger.info("Startup synchronization starting")

        # 1. Ensure repository exists
        if not self._repo_path.exists() or not (self._repo_path / ".git").exists():
            logger.info("Repository not found, cloning...")
            if not self._clone_repository():
                logger.error("Clone failed")
                return False
        else:
            logger.info("Repository exists, connecting...")
            if not self._provider.connect():
                logger.error("Failed to connect to repository")
                return False

        # 2. Fetch remote (must succeed)
        if not self._fetch_remote():
            logger.error("Fetch failed, remote unavailable. Cannot proceed.")
            return False

        # 3. Always reset local to remote (source of truth)
        logger.info("Resetting local repository to remote (source of truth)")
        if not self._reset_to_remote():
            logger.error("Reset to remote failed")
            return False

        # 4. Always apply repository database to runtime
        if not self._apply_runtime_database():
            logger.error("Failed to apply repository database to runtime")
            return False

        # 5. Refresh database sessions
        self._refresh_database_sessions()

        logger.info("Startup synchronization completed successfully")
        return True

    def _clone_repository(self) -> bool:
        try:
            self._repo_path.parent.mkdir(parents=True, exist_ok=True)
            result = self._provider.clone(progress_callback=None)
            if result:
                logger.info(f"Repository cloned successfully to {self._repo_path}")
            return result
        except Exception as e:
            logger.exception(f"Clone failed: {e}")
            return False

    def _fetch_remote(self) -> bool:
        try:
            return self._provider.fetch()
        except Exception as e:
            logger.warning(f"Fetch failed: {e}")
            return False

    def _reset_to_remote(self) -> bool:
        """Reset local repository to match remote branch."""
        try:
            return self._provider.reset_to_remote()
        except Exception as e:
            logger.exception(f"Reset to remote failed: {e}")
            return False

    def _apply_runtime_database(self) -> bool:
        """Copy repository database and manifest to runtime, update metadata."""
        repo_db = self._repo_path / "database" / "center.db"
        if not repo_db.exists():
            logger.error(f"Repository database not found: {repo_db}")
            return False

        self._runtime_db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Copy database using binary read/write
            with open(repo_db, 'rb') as fsrc:
                with open(self._runtime_db_path, 'wb') as fdst:
                    fdst.write(fsrc.read())
                    fdst.flush()
                    os.fsync(fdst.fileno())
            
            # Verify
            if self._runtime_db_path.exists() and repo_db.exists():
                src_size = repo_db.stat().st_size
                dst_size = self._runtime_db_path.stat().st_size
                logger.info(f"Runtime database updated: src_size={src_size}, dst_size={dst_size}")
                if src_size != dst_size:
                    logger.warning(f"Size mismatch after copy: src={src_size}, dst={dst_size}")
            else:
                logger.warning("Runtime database copy may have failed")

            logger.info(f"Runtime database updated from repository: {self._runtime_db_path}")

            # Business documents are versioned in the repository alongside the
            # database. Materialize Employee attachments into runtime so every
            # client can open the same files after startup synchronization.
            self._sync_employee_attachments_from_repository()

            # Copy manifest
            repo_manifest = self._repo_path / "manifest.json"
            if repo_manifest.exists():
                with open(repo_manifest, 'rb') as fsrc:
                    with open(self._runtime_manifest_path, 'wb') as fdst:
                        fdst.write(fsrc.read())
                        fdst.flush()
                        os.fsync(fdst.fileno())
                logger.info(f"Runtime manifest updated from repository: {self._runtime_manifest_path}")

                # Update metadata/version.json
                with open(repo_manifest, 'r', encoding='utf-8') as f:
                    manifest_data = json.load(f)
                runtime_version = manifest_data.get("runtime_version")
                if runtime_version is not None:
                    meta_version_path = self._metadata_dir / "version.json"
                    meta_version_path.parent.mkdir(parents=True, exist_ok=True)
                    if meta_version_path.exists():
                        with open(meta_version_path, 'r', encoding='utf-8') as f:
                            meta_data = json.load(f)
                    else:
                        meta_data = {}
                    meta_data["platform_version"] = runtime_version
                    meta_data.pop("pending_version", None)
                    with open(meta_version_path, 'w', encoding='utf-8') as f:
                        json.dump(meta_data, f, indent=2, ensure_ascii=False)
                        f.flush()
                        os.fsync(f.fileno())
                    logger.info(f"Metadata version.json updated to platform_version={runtime_version}")
            else:
                logger.warning("Repository manifest not found, skipping copy")

            return True
        except Exception as e:
            logger.exception(f"Failed to copy runtime data: {e}")
            return False

    def _sync_employee_attachments_from_repository(self) -> None:
        """Mirror repository Employee attachments into the local runtime.

        The repository is the collaboration source of truth. Runtime/Attachments
        is only the local materialized copy used by the desktop UI.
        """
        repo_root = self._repo_path / "Attachments" / "Employees"
        runtime_root = self._paths.runtime_root / "Attachments" / "Employees"
        try:
            if runtime_root.exists():
                shutil.rmtree(runtime_root)
            if repo_root.exists():
                runtime_root.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(repo_root, runtime_root)
                logger.info(
                    "Employee attachments synchronized from repository: %s -> %s",
                    repo_root, runtime_root,
                )
            else:
                logger.info("No Employee attachments found in repository; runtime mirror cleared.")
        except Exception:
            logger.exception("Failed to synchronize Employee attachments from repository")
            raise

    def _refresh_database_sessions(self):
        try:
            from centermanager.database.session import refresh_runtime_db
            refresh_runtime_db()
            logger.info("Database sessions refreshed")
        except Exception as e:
            logger.exception(f"Failed to refresh database sessions: {e}")