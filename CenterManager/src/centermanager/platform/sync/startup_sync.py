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
from centermanager.platform.synchronization.git_repository_hygiene import (
    remove_windows_shell_metadata_from_git_refs,
)
from centermanager.database.startup_security import (
    inspect_authoritative_database_for_startup,
)

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
            # Cross-machine portable deployments are sometimes placed inside
            # Windows/cloud-synced folders. Those folders can create
            # desktop.ini under .git/refs, which Git interprets as a corrupt
            # ref ("fatal: bad object refs/.../desktop.ini"). Remove only that
            # known OS metadata before opening/fetching the repository.
            if not remove_windows_shell_metadata_from_git_refs(self._repo_path):
                logger.error("Git refs hygiene failed. Cannot proceed safely.")
                return False

            logger.info("Repository exists, connecting...")
            if not self._provider.connect():
                logger.error("Failed to connect to repository")
                return False

        # A freshly cloned repository should not contain shell metadata, but
        # running the same narrow hygiene check here also covers a file created
        # between clone/connect and the authoritative fetch.
        if not remove_windows_shell_metadata_from_git_refs(self._repo_path):
            logger.error("Git refs hygiene failed before fetch. Cannot proceed safely.")
            return False

        # 2. Fetch remote (must succeed)
        if not self._fetch_remote():
            logger.error("Fetch failed, remote unavailable. Cannot proceed.")
            return False

        # A local WRITE receipt may be absent or unresolved after an EXE upgrade.
        # Remote MAIN wins only after fresh Git proof and a durable local capture.
        if not self._prepare_authoritative_startup_replacement():
            return False

        # 3. Always reset local to remote (source of truth)
        logger.info("Resetting local repository to remote (source of truth)")
        if not self._reset_to_remote():
            logger.error("Reset to remote failed")
            return False

        # 4. Validate the authoritative DB *before* copying it into runtime.
        # Normal startup must never invent a new workspace key or implicitly
        # migrate a plaintext collaboration DB because all clients must share
        # the same controlled encryption state.
        if not self._preflight_authoritative_database():
            return False

        # 5. Always apply repository database to runtime
        if not self._apply_runtime_database():
            logger.error("Failed to apply repository database to runtime")
            return False

        # 6. Refresh database sessions. This is part of startup correctness,
        # not best-effort logging: a copied DB that cannot be opened must make
        # synchronization fail closed.
        if not self._refresh_database_sessions():
            return False

        from centermanager.platform.write_recovery import WriteRecoveryJournal
        WriteRecoveryJournal().record_synchronized()
        logger.info("Startup synchronization completed successfully")
        return True

    def _prepare_authoritative_startup_replacement(self) -> bool:
        """Approve Git-MAIN-wins startup without silently discarding local work.

        Fetch and independently observe exact accepted MAIN before touching the
        local repository or DB.  When legacy/unaccepted data exist, preserve a
        verified recovery capture and issue the existing RECONCILED receipt.
        This never pushes local data or changes remote WRITE ownership.
        """
        from centermanager.platform.write_recovery import (
            WriteRecoveryJournal, RecoveryRequired,
        )
        journal = WriteRecoveryJournal()
        try:
            # Always pin the accepted ref even for an already-clean workspace.
            # Otherwise a second fetch/reset may silently install another MAIN.
            accepted = self._provider.get_fetched_remote_main_commit()
            observed = self._provider.observe_remote_main_commit()
            if not accepted or not observed or accepted != observed:
                raise RecoveryRequired(
                    "Git MAIN cannot be independently verified; local work was not replaced."
                )
            self._accepted_startup_main_oid = accepted
            try:
                journal.assert_replaceable(legacy=True)
                return True
            except RecoveryRequired:
                pass
            existing = journal.inspect()
            if existing is not None:
                base = existing.get("base_main_oid")
                if not base:
                    raise RecoveryRequired("Recovery base is missing; preserve local data.")
            else:
                # For a legacy workspace, its current local commit is the
                # only defensible base for a newly created recovery receipt.
                base = self._provider.get_local_main_commit()
                if not base:
                    raise RecoveryRequired("Legacy local Git base is unavailable.")
            journal.reconcile(
                base_oid=base,
                accepted_main=accepted,
                observe_main=self._provider.observe_remote_main_commit,
            )
            journal.assert_replaceable()
            logger.warning(
                "Startup: captured unaccepted local workspace; Git MAIN %s will replace it",
                accepted,
            )
            return True
        except Exception as exc:
            self.recovery_error = str(exc)
            logger.exception("Git-authoritative startup preflight blocked safely")
            return False

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
        """Reset to exactly the already-fetched, independently observed MAIN."""
        try:
            accepted = getattr(self, "_accepted_startup_main_oid", None)
            if not accepted or len(accepted) != 40 or any(c not in "0123456789abcdef" for c in accepted.lower()):
                logger.error("Startup accepted MAIN commit is missing or invalid")
                return False
            # Do not let provider.reset_to_remote() fetch a different generation
            # after a recovery capture has already pinned the accepted commit.
            self._provider._run_git_command(["reset", "--hard", accepted])
            actual = self._provider.get_local_main_commit()
            if actual != accepted:
                logger.error("Startup reset did not install the pinned MAIN commit")
                return False
            if self._provider.observe_remote_main_commit() != accepted:
                logger.error("Remote MAIN changed after preflight; do not install runtime database")
                return False
            return True
        except Exception as e:
            logger.exception("Pinned MAIN reset failed: %s", e)
            return False

    def _preflight_authoritative_database(self) -> bool:
        repo_db = self._repo_path / "database" / "center.db"
        result = inspect_authoritative_database_for_startup(repo_db)
        if result.ready:
            logger.info("Authoritative database security preflight passed")
            return True
        logger.error(
            "Authoritative database security preflight failed: state=%s; %s",
            result.state.value,
            result.message,
        )
        return False

    def _install_authoritative_database_atomically(self, repo_db: Path) -> bool:
        """Stage validated MAIN, fence DB handles, atomically replace and rollback."""
        import hashlib
        import uuid
        from centermanager.database import session as session_module
        from centermanager.database.artifact_security import validate_database_artifact
        from centermanager.database.encryption import (
            database_encryption_required, DatabaseKeyStore,
        )

        dest = self._runtime_db_path
        token = uuid.uuid4().hex
        stage = dest.with_name(f".{dest.name}.startup-{token}.tmp")
        previous = dest.with_name(f".{dest.name}.previous-{token}")
        sidecars = [dest.with_name(dest.name + suffix) for suffix in ("-wal", "-shm", "-journal")]
        backups = [(p, p.with_name(f".{p.name}.previous-{token}")) for p in sidecars]
        moved_sidecars = []
        moved_db = installed = fenced = succeeded = False
        try:
            with repo_db.open("rb") as source, stage.open("xb") as target:
                shutil.copyfileobj(source, target, 1024 * 1024)
                target.flush()
                os.fsync(target.fileno())
            encrypted = database_encryption_required()
            key = DatabaseKeyStore().load() if encrypted else None
            validate_database_artifact(
                stage, encryption_required=encrypted, key=key,
            )
            expected = hashlib.sha256(stage.read_bytes()).digest()

            session_module.quiesce_runtime_db()
            fenced = True
            if dest.exists():
                os.replace(dest, previous)
                moved_db = True
            for live, backup in backups:
                if live.exists():
                    os.replace(live, backup)
                    moved_sidecars.append((live, backup))
            os.replace(stage, dest)
            installed = True
            if hashlib.sha256(dest.read_bytes()).digest() != expected:
                raise RuntimeError("Installed Git MAIN database checksum mismatch")
            succeeded = True
            logger.info("Authoritative database atomically installed; stale WAL detached")
            # Caller refreshes sessions after finishing manifest and metadata.
            return True
        except Exception:
            logger.exception("Startup SQLCipher atomic install failed")
            if fenced:
                try:
                    if installed:
                        dest.unlink(missing_ok=True)
                    if moved_db:
                        os.replace(previous, dest)
                    for live, backup in moved_sidecars:
                        os.replace(backup, live)
                    session_module.refresh_runtime_db()
                except Exception:
                    logger.exception("Startup rollback failed; keep maintenance fence")
            return False
        finally:
            stage.unlink(missing_ok=True)
            # Preserve old copies until the replacement is completed.  Once
            # installed and validated, the discarded generation must not replay.
            if succeeded:
                previous.unlink(missing_ok=True)
                for _, backup in moved_sidecars:
                    backup.unlink(missing_ok=True)

    def _apply_runtime_database(self) -> bool:
        """Copy repository database and manifest to runtime, update metadata."""
        from centermanager.platform.write_recovery import require_replaceable
        require_replaceable()
        repo_db = self._repo_path / "database" / "center.db"
        if not repo_db.exists():
            logger.error(f"Repository database not found: {repo_db}")
            return False

        self._runtime_db_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Never truncate a live SQLCipher database or let stale WAL/SHM
            # from the discarded local generation replay onto accepted MAIN.
            if not self._install_authoritative_database_atomically(repo_db):
                return False

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
        runtime_root = self._paths.attachment_dir / "Employees"
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

    def _refresh_database_sessions(self) -> bool:
        try:
            from centermanager.database.session import refresh_runtime_db
            refresh_runtime_db()
            logger.info("Database sessions refreshed")
            return True
        except Exception as e:
            logger.exception(f"Failed to refresh database sessions: {e}")
            return False
