# -*- coding: utf-8 -*-
"""BootstrapManager - Application startup orchestration."""

import logging
import platform
from typing import Optional

from centermanager.core.paths import get_paths
from centermanager.core.config import get_config
from centermanager.platform.context import (
    PlatformContext,
    RuntimeContext,
    DeploymentContext,
    SessionContext,
    WorkspaceContext,
    UserContext,
    ConfigurationContext,
)
from centermanager.platform.lifecycle import PlatformLifecycle, PlatformLifecycleState
from centermanager.platform.runtime.context.runtime_state import RuntimeStateMachine, RuntimeState
from centermanager.platform.runtime.context.runtime_manifest import RuntimeManifest
from centermanager.platform.runtime.context.runtime_version import RuntimeVersion
from centermanager.platform.workspace import WorkspaceRegistry
from centermanager.platform.repository import RepositoryManager, RepositoryState, AtomicFileWriter
from centermanager.platform.runtime.context_manager import RuntimeContextManager


logger = logging.getLogger(__name__)


class BootstrapManager:
    """
    Orchestrates platform startup up to READY state.
    Does NOT authenticate user or create session.

    Git is the production database source of truth. Bootstrap therefore requires
    valid Git configuration and a successful startup synchronization before the
    runtime is declared READY. A missing runtime database is never replaced by
    an empty production database during this sequence.
    """

    def __init__(self):
        self._lifecycle = PlatformLifecycle()
        self._context: Optional[PlatformContext] = None
        self._workspace_registry = WorkspaceRegistry()
        self._repo_manager = RepositoryManager()
        self._context_manager = RuntimeContextManager()

    def run(self) -> bool:
        """Execute startup sequence."""
        try:
            self._lifecycle.transition_to(PlatformLifecycleState.INITIALIZING)
            logger.info("[BOOTSTRAP] Starting platform")

            # 1. Load configuration and create the filesystem runtime shell.
            config = get_config().raw
            paths = get_paths()

            repo_state = self._repo_manager.detect()
            logger.info(f"[BOOTSTRAP] Repository state: {repo_state.value}")

            if repo_state in (RepositoryState.NOT_FOUND, RepositoryState.INVALID):
                logger.info("[BOOTSTRAP] Creating default runtime")
                self._create_default_runtime(paths)
                self._repo_manager.refresh()
                repo_state = self._repo_manager.detect()

            if repo_state in (RepositoryState.INVALID, RepositoryState.CORRUPTED):
                logger.error(f"[BOOTSTRAP] Repository {repo_state.value}, cannot proceed")
                self._lifecycle.transition_to(PlatformLifecycleState.STOPPED)
                return False

            # 2. The remote Git repository is authoritative. Ensure credentials
            # exist, prompt on first run when they do not, then materialize the
            # repository database into runtime before any database engine opens.
            if not self._ensure_authoritative_runtime_database(paths):
                self._lifecycle.transition_to(PlatformLifecycleState.STOPPED)
                return False

            # Synchronization can replace manifest/runtime files. Refresh the
            # repository view before building contexts from the authoritative
            # materialized runtime.
            self._repo_manager.refresh()
            repo_state = self._repo_manager.detect()
            if repo_state in (RepositoryState.INVALID, RepositoryState.CORRUPTED):
                logger.error(
                    "[BOOTSTRAP] Authoritative runtime is %s after synchronization",
                    repo_state.value,
                )
                self._lifecycle.transition_to(PlatformLifecycleState.STOPPED)
                return False

            # 3. Build contexts after Git source-of-truth materialization.
            runtime_context = self._build_runtime_context(paths)
            deployment_context = self._build_deployment_context(config)
            configuration_context = ConfigurationContext.from_app_config(config)
            session_context = SessionContext()
            workspace_context = WorkspaceContext()
            user_context = UserContext()

            self._context = PlatformContext(
                runtime=runtime_context,
                deployment=deployment_context,
                session=session_context,
                workspace=workspace_context,
                user=user_context,
                configuration=configuration_context,
            )
            self._context_manager.install_context(runtime_context)

            self._context.runtime.state.transition_to(RuntimeState.CHECK_REPOSITORY)

            if not self._repo_manager.validate():
                logger.error("[BOOTSTRAP] Runtime validation failed")
                self._context.runtime.state.transition_to(RuntimeState.ERROR)
                self._lifecycle.transition_to(PlatformLifecycleState.STOPPED)
                return False

            self._context.runtime.state.transition_to(RuntimeState.READY)
            self._lifecycle.transition_to(PlatformLifecycleState.READY)
            logger.info("[BOOTSTRAP] Platform ready")
            return True

        except Exception as e:
            logger.exception(f"[BOOTSTRAP] Fatal error: {e}")
            self._lifecycle.transition_to(PlatformLifecycleState.STOPPED)
            return False

    def _ensure_authoritative_runtime_database(self, paths) -> bool:
        """Require Git config and install the remote database into runtime.

        This method runs only after QApplication has been created by app.main(),
        so the first-run Git configuration dialog can be shown safely.
        """
        # Local imports avoid widening the bootstrap module import graph and
        # keep UI/Git dependencies out of module initialization.
        from centermanager.core.git_locator import locate_git
        from centermanager.services.git_config_service import GitConfigService
        from centermanager.ui.git_config_dialog import GitConfigDialog
        from centermanager.platform.synchronization import GitSynchronizationProvider
        from centermanager.platform.sync import StartupSynchronization
        from centermanager.database.lifecycle import DatabaseLifecycle, DatabaseLifecycleState

        git_executable = locate_git()
        if not git_executable:
            logger.error("[BOOTSTRAP] Git executable is required but was not found")
            return False

        git_config_service = GitConfigService()
        git_config = git_config_service.get_config() if git_config_service.has_config() else None

        if git_config is None:
            logger.info("[BOOTSTRAP] Git configuration missing or invalid; requesting first-run configuration")
            dialog = GitConfigDialog(git_config_service)
            if dialog.exec() != dialog.DialogCode.Accepted:
                logger.warning("[BOOTSTRAP] Git configuration cancelled; startup aborted")
                return False
            git_config = git_config_service.get_config()
            if git_config is None:
                logger.error("[BOOTSTRAP] Git configuration was not available after first-run dialog")
                return False

        provider = GitSynchronizationProvider(
            repo_path=paths.runtime_root / "repository",
            repository_url=git_config.repository_url,
            token=git_config.token,
            username=git_config.username,
            branch=git_config.branch,
            email=git_config.email or "",
            git_executable=str(git_executable),
        )

        logger.info("[BOOTSTRAP] Synchronizing authoritative Git runtime")
        if not StartupSynchronization(provider).run():
            logger.error("[BOOTSTRAP] Authoritative Git synchronization failed")
            return False

        runtime_db = paths.database_dir / "center.db"
        state = DatabaseLifecycle(runtime_db).inspect()
        if state is not DatabaseLifecycleState.AVAILABLE:
            logger.error(
                "[BOOTSTRAP] Git synchronization did not materialize a usable database: state=%s",
                state.value,
            )
            return False

        logger.info("[BOOTSTRAP] Authoritative Git database materialized successfully")
        return True

    def _create_default_runtime(self, paths) -> None:
        """Create the filesystem/runtime shell only; never create business DB data."""
        paths.ensure_directories()

        manifest = RuntimeManifest(
            runtime_version=1,
            database_version=1,
            minimum_app_version="0.1.0",
        )
        writer = AtomicFileWriter(paths.runtime_root / "manifest.json")
        writer.write_json(manifest.to_dict())
        logger.info("[BOOTSTRAP] Default runtime created")

    def _build_runtime_context(self, paths) -> RuntimeContext:
        """Build RuntimeContext from disk."""
        try:
            manifest = self._repo_manager._manifest_loader.load()
        except Exception:
            manifest = RuntimeManifest()
        return RuntimeContext(
            manifest=manifest,
            state=RuntimeStateMachine(),
            version=RuntimeVersion(current=manifest.runtime_version),
            machine_id=platform.node(),
        )

    def _build_deployment_context(self, config: dict) -> DeploymentContext:
        """Build DeploymentContext from config."""
        git_config = config.get("git", {})
        return DeploymentContext(
            profile=config.get("deployment", {}).get("profile", "standalone"),
            repository_url=git_config.get("repository_url"),
            branch=git_config.get("branch", "main"),
            local_path=git_config.get("local_path"),
            git_configured=bool(git_config.get("repository_url") and git_config.get("token")),
        )

    def get_context(self) -> PlatformContext:
        """Get platform context after bootstrap."""
        if self._context is None:
            raise RuntimeError("Bootstrap not run yet")
        return self._context

    def get_workspace_registry(self) -> WorkspaceRegistry:
        """Get workspace registry."""
        return self._workspace_registry

    def get_lifecycle(self) -> PlatformLifecycle:
        """Get platform lifecycle."""
        return self._lifecycle

    def get_repository_manager(self) -> RepositoryManager:
        """Get repository manager."""
        return self._repo_manager
