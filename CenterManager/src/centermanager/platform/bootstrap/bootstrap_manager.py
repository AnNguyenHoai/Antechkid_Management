# -*- coding: utf-8 -*-
"""BootstrapManager - Application startup orchestration."""

import logging
import platform
import uuid
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
            
            # 1. Load configuration
            config = get_config().raw
            paths = get_paths()
            
            # 2. Detect repository state
            repo_state = self._repo_manager.detect()
            logger.info(f"[BOOTSTRAP] Repository state: {repo_state.value}")
            
            # 3. If not ready, create default runtime
            if repo_state in (RepositoryState.NOT_FOUND, RepositoryState.INVALID):
                logger.info("[BOOTSTRAP] Creating default runtime")
                self._create_default_runtime(paths)
                self._repo_manager.refresh()  # Xóa cache để detect lại
                repo_state = self._repo_manager.detect()
            
            # 4. If still invalid or corrupted, cannot proceed
            if repo_state in (RepositoryState.INVALID, RepositoryState.CORRUPTED):
                logger.error(f"[BOOTSTRAP] Repository {repo_state.value}, cannot proceed")
                self._lifecycle.transition_to(PlatformLifecycleState.STOPPED)
                return False
            
            # 5. Build contexts
            runtime_context = self._build_runtime_context(paths)
            deployment_context = self._build_deployment_context(config)
            configuration_context = ConfigurationContext.from_app_config(config)
            session_context = SessionContext()
            workspace_context = WorkspaceContext()
            user_context = UserContext()
            
            # 6. Aggregate into PlatformContext
            self._context = PlatformContext(
                runtime=runtime_context,
                deployment=deployment_context,
                session=session_context,
                workspace=workspace_context,
                user=user_context,
                configuration=configuration_context,
            )
            self._context_manager._context = self._context
            # 7. Transition runtime state to CHECK_REPOSITORY
            self._context.runtime.state.transition_to(RuntimeState.CHECK_REPOSITORY)
            
            # 8. Validate runtime (quick check)
            if not self._repo_manager.validate():
                logger.error("[BOOTSTRAP] Runtime validation failed")
                self._context.runtime.state.transition_to(RuntimeState.ERROR)
                self._lifecycle.transition_to(PlatformLifecycleState.STOPPED)
                return False
            
            # 9. Runtime ready
            self._context.runtime.state.transition_to(RuntimeState.READY)
            self._lifecycle.transition_to(PlatformLifecycleState.READY)
            logger.info("[BOOTSTRAP] Platform ready")
            return True
            
        except Exception as e:
            logger.exception(f"[BOOTSTRAP] Fatal error: {e}")
            self._lifecycle.transition_to(PlatformLifecycleState.STOPPED)
            return False
    
    def _create_default_runtime(self, paths) -> None:
        """Create default runtime structure and manifest."""
        # Ensure directories (tạo tất cả thư mục runtime)
        paths.ensure_directories()
        
        # Tạo thêm các thư mục cần thiết cho RuntimeValidator
        required_dirs = ["database", "metadata", "reports", "attachments", "collaboration"]
        for dir_name in required_dirs:
            (paths.runtime_root / dir_name).mkdir(parents=True, exist_ok=True)
        
        # Create default manifest
        manifest = RuntimeManifest(
            runtime_version=1,
            database_version=1,
            minimum_app_version="0.1.0",
        )
        
        # Write manifest using AtomicFileWriter
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