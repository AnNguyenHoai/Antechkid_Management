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
        self.remote_unavailable = False

    def _fresh_install_eligible(self, journal) -> bool:
        """Only grant startup provenance to a workspace with no prior data.

        Existing PDFs are derived/rebuildable, whereas any DB/WAL,
        attachment, Git working tree or recovery capture is protected.
        """
        roots = journal._workspace_roots()

        def has_material(root, *, allow_placeholders=False):
            root = Path(root)
            if not root.exists():
                return False
            if root.is_symlink() or not root.is_dir():
                return True
            return any(
                item.is_symlink() or (
                    item.is_file() and not (
                        allow_placeholders and item.name in {'.gitkeep', '.keep'}
                    )
                )
                for item in root.rglob('*')
            )

        has_repository = (
            self._repo_path.is_symlink() or
            (self._repo_path.exists() and (
                not self._repo_path.is_dir() or any(self._repo_path.iterdir())
            ))
        )
        recovery_material = has_material(journal.root)
        business_material = any(
            has_material(roots[name], allow_placeholders=True)
            for name in ('database', 'attachments', 'legacy-attachments')
        )
        fresh_install = (
            not self._runtime_db_path.exists()
            and not has_repository
            and not recovery_material
            and not business_material
        )
        logger.info(
            "Fresh-install eligibility: eligible=%s db_present=%s "
            "repository_material=%s recovery_material=%s business_material=%s",
            fresh_install, self._runtime_db_path.exists(), has_repository,
            recovery_material, business_material,
        )
        return fresh_install

    def run(self) -> bool:
        """Execute startup synchronization."""
        logger.info("Startup synchronization starting")
        # Only a genuinely empty first-time install may receive a new CLEAN
        # receipt after the app's explicitly authorized Alembic migration.
        # Existing DBs, Git worktrees and journals must keep their recovery
        # provenance; absence of a receipt alone proves nothing.
        from centermanager.platform.write_recovery import WriteRecoveryJournal
        _journal = WriteRecoveryJournal()
        fresh_install = self._fresh_install_eligible(_journal)
        self._initial_main_receipt_allowed = fresh_install
        self._manual_review_backup = None
        # A previous process may have died between individually atomic
        # filesystem renames.  Neither Git reset nor journal reconciliation
        # may run until an incomplete installation is explicitly recovered.
        if not self._check_interrupted_startup_install():
            return False

        # 1. Ensure repository exists
        if not self._repo_path.exists() or not (self._repo_path / ".git").exists():
            logger.info("Repository not found, cloning...")
            if not self._preserve_missing_repository_runtime():
                return False
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
            # Only this point permits a later, separately authenticated
            # Offline READ fallback. Git/recovery/identity failures after
            # fetching MAIN must never be converted to a cache fallback.
            self.remote_unavailable = True
            logger.error("Fetch failed, remote unavailable. Cannot proceed online.")
            return False

        # A local WRITE receipt may be absent or unresolved after an EXE upgrade.
        # Remote MAIN wins only after fresh Git proof and a durable local capture.
        if not self._prepare_authoritative_startup_replacement():
            return False

        # Record the pre-reset local revision for rollback on downstream failure.
        self._startup_previous_local_oid = self._provider.get_local_main_commit()
        # 3. Always reset local to remote (source of truth)
        logger.info("Resetting local repository to remote (source of truth)")
        if not self._reset_to_remote():
            logger.error("Reset to remote failed")
            self._rollback_startup_git_repository()
            return False

        # 4. Validate the authoritative DB *before* copying it into runtime.
        # Normal startup must never invent a new workspace key or implicitly
        # migrate a plaintext collaboration DB because all clients must share
        # the same controlled encryption state.
        if not self._preflight_authoritative_database():
            self._rollback_startup_git_repository()
            return False

        # 5. Always apply repository database to runtime
        if not self._apply_runtime_database():
            logger.error("Failed to apply repository database to runtime")
            self._rollback_failed_install_all()
            return False

        # 6. Refresh database sessions. This is part of startup correctness,
        # not best-effort logging: a copied DB that cannot be opened must make
        # synchronization fail closed.
        if not self._refresh_database_sessions():
            self._rollback_failed_install_all()
            return False

        try:
            from centermanager.platform.write_recovery import WriteRecoveryJournal
            if not getattr(self, "_manual_reset_requested", False):
                WriteRecoveryJournal().record_synchronized()
        except Exception:
            logger.exception("Startup recovery receipt verification failed; rolling back runtime DB")
            self._rollback_startup_database_install()
            self._rollback_startup_assets()
            self._rollback_startup_git_repository()
            self._complete_failed_startup_rollback()
            return False
        self._finalize_startup_database_install()
        self._finalize_startup_assets()
        self._complete_startup_install()
        self._startup_previous_local_oid = None
        if getattr(self, "_manual_reset_requested", False):
            # This one-time capability is consumed by app.py only after
            # Alembic and identity checks, before login/WRITE.
            self._provider._verified_manual_main_oid = self._accepted_startup_main_oid
            self._provider._verified_manual_backup_path = str(self._manual_review_backup.resolve())
        if self._initial_main_receipt_allowed:
            # No previous active journal was silently promoted. Any legacy
            # files were copied and verified before Git MAIN replacement.
            # This in-process proof is consumed immediately after ensure_schema.
            # Never persist a marker that could outlive a crash or EXE update.
            self._provider._fresh_install_main_oid = self._accepted_startup_main_oid
            logger.info("Verified MAIN bootstrap: deferring new CLEAN receipt until schema verification")
        logger.info("Startup synchronization completed successfully")
        return True

    def _startup_install_marker_path(self) -> Path:
        """Location never included in the runtime journal fingerprint."""
        runtime_root = self._runtime_db_path.parent.parent.resolve()
        return (
            runtime_root.with_name(runtime_root.name + ".write-recovery")
            / "startup-install.pending.json"
        )

    def _startup_replay_targets(self):
        db = self._runtime_db_path
        return (
            ("database", db),
            ("wal", db.with_name(db.name + "-wal")),
            ("shm", db.with_name(db.name + "-shm")),
            ("journal", db.with_name(db.name + "-journal")),
            ("employees", self._paths.attachment_dir / "Employees"),
            ("manifest", self._runtime_manifest_path),
            ("version", self._metadata_dir / "version.json"),
        )

    def _check_interrupted_startup_install(self) -> bool:
        marker = self._startup_install_marker_path()
        if not marker.exists():
            return True
        from centermanager.platform.sync.startup_install_replay import (
            recover_interrupted_install, InterruptedInstallError,
        )
        try:
            # No production engine or Git publication is allowed here. A
            # recovered old snapshot remains temporary until fetch and exact
            # Git MAIN install succeed later in run().
            from centermanager.database import session as session_module
            session_module.quiesce_runtime_db()
            recover_interrupted_install(marker, self._startup_replay_targets())
            # Replay has restored and verified the original files. No live
            # process is allowed to use them yet (startup/login has not
            # completed), but the process-global maintenance flag MUST be
            # released so Git MAIN preflight and SQLCipher validation can run.
            # The authoritative install will acquire its own fence.
            session_module.end_runtime_db_maintenance()
            logger.warning(
                "Interrupted local install restored from verified snapshot; "
                "normal Git MAIN synchronization is still mandatory"
            )
            return True
        except (InterruptedInstallError, OSError, RuntimeError):
            self.recovery_error = (
                "Interrupted startup installation could not be verified or "
                "recovered. Preserve runtime and .write-recovery; startup blocked."
            )
            logger.exception("%s", self.recovery_error)
            return False

    def _begin_startup_install(self) -> None:
        """Persist original DB/WAL/asset bytes before any live replacement."""
        from centermanager.platform.sync.startup_install_replay import capture_before_install
        from centermanager.database import session as session_module
        # Preexisting WAL must not change while its bytes are captured.
        session_module.quiesce_runtime_db()
        marker = self._startup_install_marker_path()
        capture_before_install(
            marker, self._startup_replay_targets(),
            getattr(self, "_accepted_startup_main_oid", None),
        )
        self._startup_pending_install = marker

    def _rollback_failed_install_all(self) -> None:
        """Attempt every rollback even if one artifact cannot be restored.

        Failure to roll back attachments must not suppress restoration of the
        SQLCipher database and vice versa. Leave the marker if any fails.
        """
        failures = []
        for name, action in (
            ("database", self._rollback_startup_database_install),
            ("assets", self._rollback_startup_assets),
            ("git", self._rollback_startup_git_repository),
        ):
            try:
                action()
            except Exception as exc:
                failures.append(name)
                logger.exception("Startup %s rollback failed: %s", name, exc)
        if failures:
            logger.error("Incomplete startup rollback (%s); pending marker retained", failures)
            return
        self._complete_failed_startup_rollback()

    def _complete_failed_startup_rollback(self) -> None:
        """Remove pending marker only if every in-process rollback completed.

        If any DB backup, asset snapshot or Git previous HEAD remains, preserve
        the marker and block the next boot for explicit recovery.
        """
        if (getattr(self, "_startup_db_install_backup", None) is None
                and getattr(self, "_startup_assets", None) is None
                and not getattr(self, "_startup_previous_local_oid", None)):
            self._complete_startup_install()
        else:
            logger.error("Startup rollback incomplete; interruption marker retained")

    def _complete_startup_install(self) -> None:
        """Clear the barrier only after all startup acceptance gates pass."""
        marker = getattr(self, "_startup_pending_install", None)
        if marker is not None:
            marker.unlink()
            self._startup_pending_install = None

    def _rollback_startup_git_repository(self) -> None:
        """Restore prior tracked Git generation after a failed startup install.

        The recovery capture remains authoritative for any untracked work.
        This never modifies the remote or WRITE lock.
        """
        previous = getattr(self, "_startup_previous_local_oid", None)
        if not previous:
            return
        try:
            self._provider._run_git_command(["reset", "--hard", previous])
            if self._provider.get_local_main_commit() != previous:
                raise RuntimeError("Local repository rollback OID mismatch")
            self._startup_previous_local_oid = None
        except Exception:
            logger.exception("Startup Git rollback failed: retain recovery artifacts; do not proceed")

    def _prepare_authoritative_startup_replacement(self) -> bool:
        """Git MAIN First: keep ONE active DB and archive unaccepted local bytes.

        Historical Recovery metadata is evidence for manual review, not a
        condition for using an independently observed authoritative MAIN.
        Never overwrite a local DB/WAL/journal until a verified separate copy
        exists. Nothing from the archive can be published automatically.
        """
        from centermanager.platform.write_recovery import WriteRecoveryJournal
        from centermanager.platform.sync.manual_review_backup import (
            preserve_workspace_for_manual_review, verify_manual_review_backup,
        )
        journal = WriteRecoveryJournal()
        try:
            from centermanager.database.mutation_authority import gate_for
            gate = gate_for()
            with gate.lock:
                if not gate.closed:
                    raise RuntimeError("Cannot replace an active local editor.")
            accepted = self._provider.get_fetched_remote_main_commit()
            observed = self._provider.observe_remote_main_commit()
            if not accepted or accepted != observed:
                raise RuntimeError("Exact remote Git MAIN cannot be verified.")
            self._accepted_startup_main_oid = accepted
            self._startup_reconciled_unaccepted_local = False
            self._manual_reset_requested = False

            try:
                document = journal.inspect()
            except Exception:
                # Malformed journals are archived as raw evidence, never
                # interpreted as CLEAN or silently deleted.
                logger.warning("Legacy Recovery metadata unreadable; archiving original bytes")
                document = None

            if document and document.get("status") == "CLEAN":
                try:
                    journal.assert_replaceable()
                    return True
                except Exception:
                    logger.warning("CLEAN metadata differs from local files; archive before MAIN reset")

            if document is None and not journal.journal.exists() and self._initial_main_receipt_allowed:
                # A genuinely empty first install needs no obsolete backup.
                return True

            archive = preserve_workspace_for_manual_review(
                journal, reason="manual-review-before-authoritative-main",
            )
            verify_manual_review_backup(archive)
            self._manual_review_backup = archive
            self._startup_reconciled_unaccepted_local = True
            # A previous journal will be archived after verified MAIN install
            # and schema migration, before the new CLEAN receipt is committed.
            self._manual_reset_requested = journal.journal.exists()
            self._initial_main_receipt_allowed = not self._manual_reset_requested
            logger.warning(
                "Unpublished local workspace durably preserved for manual review; "
                "installing only verified Git MAIN"
            )
            return True
        except Exception as exc:
            self.recovery_error = str(exc)
            logger.exception("Git MAIN replacement refused: local evidence not preserved")
            return False

    def _preserve_missing_repository_runtime(self) -> bool:
        """Safeguard legacy files before first clone without bypassing clone guard.

        Never alter production Git permissions or pretend this is an accepted
        publication receipt.  The independent capture is only a rollback copy.
        """
        import hashlib
        import uuid
        from centermanager.platform.write_recovery import WriteRecoveryJournal
        journal = WriteRecoveryJournal()
        try:
            if journal.inspect() is not None:
                self.recovery_error = "Existing recovery journal requires a matching repository before clone"
                return False
            if self._repo_path.exists() and any(self._repo_path.iterdir()):
                self.recovery_error = "Incomplete repository contains files; preserve and inspect manually"
                return False
            if not self._runtime_db_path.exists():
                return True
            root = journal.root / "preclone" / uuid.uuid4().hex
            root.mkdir(parents=True, exist_ok=False)
            files = {}
            for name, source_root in journal._workspace_roots().items():
                if name == "repository":
                    continue
                source_root = Path(source_root)
                if not source_root.exists():
                    continue
                if source_root.is_symlink():
                    raise RuntimeError("Symlinked workspace cannot be preserved")
                for source in sorted(source_root.rglob("*")):
                    if source.is_symlink():
                        raise RuntimeError("Symlinked workspace file cannot be preserved")
                    if not source.is_file():
                        continue
                    rel = (Path(name) / source.relative_to(source_root)).as_posix()
                    dest = root / rel
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, dest)
                    digest = hashlib.sha256(dest.read_bytes()).hexdigest()
                    if digest != hashlib.sha256(source.read_bytes()).hexdigest():
                        raise RuntimeError("Preclone workspace capture checksum mismatch")
                    files[rel] = digest
            manifest = root / "manifest.json"
            with manifest.open("x", encoding="utf-8") as handle:
                json.dump({"files": files}, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            self._startup_preclone_capture = root
            logger.warning("Preserved missing-repository legacy workspace at %s", root)
            return True
        except Exception as exc:
            self.recovery_error = str(exc)
            logger.exception("Cannot preserve missing-repository runtime before clone")
            return False

    def _clone_repository(self) -> bool:
        try:
            self._repo_path.parent.mkdir(parents=True, exist_ok=True)
            result = self._provider.clone(progress_callback=None, preclone_capture=getattr(self, '_startup_preclone_capture', None))
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
            if getattr(self, "_manual_review_backup", None) is not None:
                # The generic Git mutation gate correctly refuses to reset
                # a dirty journal. The narrowly scoped provider command can
                # operate only on the exact verified MAIN after the ORIGINAL
                # DB/WAL/Git/Recovery has been archived with checked hashes.
                self._provider.reset_verified_main_after_manual_backup(
                    accepted, self._manual_review_backup,
                )
            else:
                self._provider._run_git_command(["reset", "--hard", accepted])
            if (getattr(self, "_startup_reconciled_unaccepted_local", False)
                    and getattr(self, "_manual_review_backup", None) is None):
                # The dedicated verified-backup path cleaned untracked files
                # inside its narrow provider command already.
                self._provider._run_git_command(["clean", "-fd"])
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
        # Keep rollback outside the runtime fingerprint, but on the *same*
        # filesystem as center.db. Windows os.replace cannot move across
        # volumes (WinError 17), including CI runtimes under another drive.
        runtime_root = dest.parent.parent.resolve()
        rollback_root = (
            runtime_root.with_name(runtime_root.name + ".write-recovery")
            / "startup-rollbacks" / token
        )
        rollback_root.mkdir(parents=True, exist_ok=False)
        previous = rollback_root / dest.name
        sidecars = [dest.with_name(dest.name + suffix) for suffix in ("-wal", "-shm", "-journal")]
        backups = [(p, rollback_root / p.name) for p in sidecars]
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
            self._startup_db_install_backup = (dest, previous, moved_db, tuple(moved_sidecars))
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
            # Keep prior DB and WAL until manifest, session refresh, and
            # recovery receipt all finish. run() finalizes or rolls back.

    def _rollback_startup_database_install(self) -> None:
        """Restore the previous DB generation if later startup phases fail."""
        saved = getattr(self, "_startup_db_install_backup", None)
        if saved is None:
            return
        from centermanager.database import session as session_module
        dest, previous, moved_db, moved_sidecars = saved
        try:
            if not session_module.runtime_db_maintenance_active():
                session_module.quiesce_runtime_db()
            dest.unlink(missing_ok=True)
            for suffix in ("-wal", "-shm", "-journal"):
                dest.with_name(dest.name + suffix).unlink(missing_ok=True)
            if moved_db:
                os.replace(previous, dest)
            for live, backup in moved_sidecars:
                os.replace(backup, live)
            session_module.refresh_runtime_db()
            self._startup_db_install_backup = None
            logger.warning("Startup failed: restored previous database and WAL generation")
        except Exception:
            logger.exception("Startup rollback failed: preserve previous files; database remains fenced")

    def _finalize_startup_database_install(self) -> None:
        """Discard old generation only after all startup integrity gates passed."""
        saved = getattr(self, "_startup_db_install_backup", None)
        if saved is None:
            return
        _, previous, _, moved_sidecars = saved
        previous.unlink(missing_ok=True)
        for _, backup in moved_sidecars:
            backup.unlink(missing_ok=True)
        self._startup_db_install_backup = None

    def _prepare_startup_assets(self) -> None:
        """Stage MAIN assets and retain an immutable, non-runtime rollback copy.

        This handles ordinary exceptions. A killed process needs a separate
        durable interrupted-install protocol (S04-01B).
        """
        import uuid
        token = uuid.uuid4().hex
        employees = self._paths.attachment_dir / "Employees"
        version = self._metadata_dir / "version.json"
        manifest = self._runtime_manifest_path
        targets = (employees, manifest, version)
        copies = []
        try:
            for dest in targets:
                # Each backup must be on the same volume as its destination,
                # and outside WriteRecoveryJournal's workspace fingerprint.
                runtime_parent = dest.parent
                while runtime_parent.name not in {"runtime", "Runtime"} and runtime_parent != runtime_parent.parent:
                    runtime_parent = runtime_parent.parent
                if runtime_parent == runtime_parent.parent:
                    runtime_parent = self._runtime_db_path.parent.parent
                rollback = (
                    runtime_parent.with_name(runtime_parent.name + ".write-recovery")
                    / "startup-assets" / token / dest.name
                )
                exists = dest.exists()
                if exists:
                    rollback.parent.mkdir(parents=True, exist_ok=True)
                    if dest.is_dir():
                        shutil.copytree(dest, rollback)
                    else:
                        shutil.copy2(dest, rollback)
                copies.append((dest, rollback, exists))
            # Ensure source attachments are completely readable before the
            # already-validated database can be installed.
            repo_employees = self._repo_path / "Attachments" / "Employees"
            if repo_employees.exists():
                staged_employees = (
                    employees.parent.parent.with_name(employees.parent.parent.name + ".write-recovery")
                    / "startup-assets" / token / "staged-employees"
                )
                staged_employees.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(repo_employees, staged_employees)
            else:
                staged_employees = None
            self._startup_assets = (copies, staged_employees)
        except Exception:
            logger.exception("Unable to stage startup assets; live workspace remains unchanged")
            raise

    def _rollback_startup_assets(self) -> None:
        saved = getattr(self, "_startup_assets", None)
        if saved is None:
            return
        copies, _ = saved
        failures = []
        for dest, backup, existed in reversed(copies):
            try:
                if dest.is_dir():
                    shutil.rmtree(dest)
                elif dest.exists():
                    dest.unlink()
                if existed:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    if backup.is_dir():
                        shutil.copytree(backup, dest)
                    else:
                        shutil.copy2(backup, dest)
            except Exception as exc:
                failures.append((str(dest), str(exc)))
                logger.exception("Startup asset rollback failed for %s", dest)
        if failures:
            raise RuntimeError("Startup assets could not all be restored: " + repr(failures))
        self._finalize_startup_assets()

    def _finalize_startup_assets(self) -> None:
        saved = getattr(self, "_startup_assets", None)
        if saved is None:
            return
        copies, staged = saved
        for _, backup, _ in copies:
            if backup.is_dir():
                shutil.rmtree(backup)
            else:
                backup.unlink(missing_ok=True)
        if staged is not None and staged.exists():
            shutil.rmtree(staged)
        self._startup_assets = None

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
            self._prepare_startup_assets()
            self._begin_startup_install()
            # Never truncate a live SQLCipher database or let stale WAL/SHM
            # from the discarded local generation replay onto accepted MAIN.
            if not self._install_authoritative_database_atomically(repo_db):
                self._rollback_startup_assets()
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
            # DB and other assets must each get a rollback attempt even when
            # the other restoration fails. The pending marker stays on disk.
            failures = []
            for name, action in (
                ("database", self._rollback_startup_database_install),
                ("assets", self._rollback_startup_assets),
            ):
                try:
                    action()
                except Exception:
                    failures.append(name)
                    logger.exception("Startup %s rollback failed", name)
            if failures:
                logger.error("Incomplete startup rollback; recovery required: %s", failures)
            return False

    def _sync_employee_attachments_from_repository(self) -> None:
        """Mirror repository Employee attachments into the local runtime.

        The repository is the collaboration source of truth. Runtime/Attachments
        is only the local materialized copy used by the desktop UI.
        """
        repo_root = self._repo_path / "Attachments" / "Employees"
        runtime_root = self._paths.attachment_dir / "Employees"
        try:
            staged = getattr(self, "_startup_assets", None)
            staged_source = staged[1] if staged is not None else None
            if runtime_root.exists():
                shutil.rmtree(runtime_root)
            if staged_source is not None:
                runtime_root.parent.mkdir(parents=True, exist_ok=True)
                os.replace(staged_source, runtime_root)
            elif repo_root.exists():
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
