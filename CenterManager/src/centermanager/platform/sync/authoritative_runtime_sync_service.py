# -*- coding: utf-8 -*-
"""Fail-closed authoritative synchronization barriers.

WRITE ownership must never become EDITING against a repository snapshot that was
selected by manifest version alone.  Git MAIN commit identity is authoritative:
every WRITE handoff fetches/resets to origin/MAIN, proves local HEAD equals the
freshly observed remote HEAD, materializes that exact repository DB into runtime,
and only then refreshes the UI projection.

Background synchronization is pull-only.  It must never publish the waiting
machine's runtime database back to MAIN.
"""

import logging
from datetime import datetime

from .status import SyncStatus
from .write_handoff_runtime_sync_service import RuntimeSyncService as _HardenedRuntimeSyncService

logger = logging.getLogger(__name__)


class RuntimeSyncService(_HardenedRuntimeSyncService):
    """Runtime sync with Git-commit-authoritative pre-WRITE fencing."""

    def _force_latest_main_repository(self):
        """Fetch/reset local repository to the current remote MAIN, fail closed.

        Returns the authoritative MAIN commit SHA on success, otherwise None.
        ``reset_to_remote`` performs a fresh fetch before the hard reset.  We then
        fetch/observe remote MAIN again and require exact SHA equality so a
        version-number equality can never bypass synchronization.
        """
        provider = self._sync_manager.provider() if self._sync_manager else None
        if provider is None:
            logger.error("Authoritative MAIN barrier unavailable: no provider")
            return None
        try:
            if not provider.health():
                logger.error("Authoritative MAIN barrier refused: provider unhealthy")
                return None
            if not provider.connect():
                logger.error("Authoritative MAIN barrier refused: provider connect failed")
                return None

            reset_to_remote = getattr(provider, "reset_to_remote", None)
            get_remote = getattr(provider, "get_remote_main_commit", None)
            get_local = getattr(provider, "get_local_main_commit", None)
            if not callable(reset_to_remote) or not callable(get_remote) or not callable(get_local):
                logger.error("Authoritative MAIN barrier refused: provider lacks commit-fence API")
                return None

            # Mandatory fresh Git synchronization.  Never gate this on
            # runtime_version: equal manifests can exist at different commits.
            if not reset_to_remote():
                logger.error("Authoritative MAIN barrier refused: fetch/reset failed")
                return None

            # get_remote_main_commit performs another fetch.  This closes the
            # window between reset and verification; if MAIN moved, local HEAD
            # will differ and WRITE is refused rather than using a stale base.
            remote_commit = get_remote()
            local_commit = get_local()
            if not remote_commit or not local_commit or local_commit != remote_commit:
                logger.error(
                    "Authoritative MAIN barrier refused: local HEAD != remote MAIN "
                    "(local=%s remote=%s)",
                    (local_commit or "missing")[:12],
                    (remote_commit or "missing")[:12],
                )
                return None

            logger.info("Authoritative MAIN pinned for WRITE handoff: %s", remote_commit[:12])
            return remote_commit
        except Exception:
            logger.exception("Authoritative MAIN barrier failed")
            return None

    def execute_write_handoff_sync(self) -> bool:
        """Always pull exact latest Git MAIN before WRITE can be granted.

        This path is intentionally independent of manifest version comparison.
        It performs no runtime->repository materialization, commit, or push.
        """
        with self._state_mutex:
            if self._status == SyncStatus.SYNCHRONIZING:
                logger.warning("WRITE handoff refused: synchronization already in progress")
                return False
            self._set_status(SyncStatus.SYNCHRONIZING)

        try:
            authoritative_commit = self._force_latest_main_repository()
            if not authoritative_commit:
                return False

            # Git -> runtime only.  The inherited hardened implementation
            # validates the repository DB, quiesces DB handles, removes stale
            # WAL/SHM, atomically installs the DB, byte-verifies it, and rebuilds
            # sessions.  It never publishes runtime state.
            if not self._apply_runtime_update():
                logger.error("WRITE handoff refused: Git-authoritative DB install failed")
                return False

            # Re-observe MAIN after DB installation.  If another writer somehow
            # moved MAIN during the boundary, do not grant WRITE on the older
            # snapshot.  The caller may retry and will fetch the newer commit.
            provider = self._sync_manager.provider()
            remote_after = provider.get_remote_main_commit()
            local_after = provider.get_local_main_commit()
            if (
                not remote_after
                or not local_after
                or remote_after != authoritative_commit
                or local_after != authoritative_commit
            ):
                logger.error(
                    "WRITE handoff refused: MAIN changed during materialization "
                    "(pinned=%s local=%s remote=%s)",
                    authoritative_commit[:12],
                    (local_after or "missing")[:12],
                    (remote_after or "missing")[:12],
                )
                return False

            if not self._write_handoff_ui_refresh.refresh():
                logger.error("WRITE handoff refused: authoritative UI refresh failed")
                return False

            self._current_version = self._get_repository_version()
            self._remote_version = self._current_version
            self._pending_update = False
            self._last_sync = datetime.now()
            logger.info(
                "WRITE handoff passed: runtime/UI derived from exact remote MAIN %s",
                authoritative_commit[:12],
            )
            return True
        except Exception:
            logger.exception("WRITE handoff authoritative barrier failed")
            return False
        finally:
            with self._state_mutex:
                self._set_status(SyncStatus.IDLE)

    def _perform_sync(self) -> bool:
        """Background synchronization is strictly remote -> local/runtime.

        The previous implementation called ``begin_sync('Auto sync', ...)``.
        A non-empty message makes SynchronizationManager materialize the stale
        runtime DB back into the repository and publish it after pulling.  That
        can erase the previous writer's freshly-published data.  Passing no
        message makes begin_sync fetch/pull/validate only.
        """
        with self._state_mutex:
            self._set_status(SyncStatus.SYNCHRONIZING)
        try:
            result = self._sync_manager.begin_sync()
            if not result or not result.is_success():
                logger.error(
                    "Pull-only synchronization failed: %s",
                    result.message if result else "no result",
                )
                return False

            if not self._apply_runtime_update():
                logger.error("Pull-only sync failed to install authoritative runtime DB")
                return False

            self._current_version = self._get_repository_version()
            self._remote_version = self._current_version
            self._pending_update = False
            self._last_sync = datetime.now()
            self._failed_count = 0
            logger.info(
                "Pull-only synchronization completed; no runtime state was published to MAIN"
            )
            return True
        except Exception:
            self._failed_count += 1
            logger.exception("Pull-only synchronization failed")
            return False
        finally:
            with self._state_mutex:
                self._set_status(SyncStatus.IDLE)
