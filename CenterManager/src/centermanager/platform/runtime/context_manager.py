# -*- coding: utf-8 -*-
"""RuntimeContextManager - Manages RuntimeContext lifecycle."""

import uuid
import platform
from typing import Optional
import logging

from centermanager.core.config import get_config
from centermanager.core.paths import get_paths

from .context.runtime_context import RuntimeContext
from .context.runtime_manifest import RuntimeManifest
from .context.runtime_state import RuntimeState, RuntimeStateMachine
from .context.runtime_configuration import RuntimeConfiguration
from .context.runtime_version import RuntimeVersion

logger = logging.getLogger(__name__)


class RuntimeContextManager:
    """Manages RuntimeContext lifecycle."""
    
    def __init__(self):
        self._context: Optional[RuntimeContext] = None
    
    def create_context(self) -> RuntimeContext:
        """Create RuntimeContext at startup."""
        config = get_config().raw
        paths = get_paths()
        
        # Load manifest if exists
        manifest = self._load_manifest(paths)
        
        # Create context
        self._context = RuntimeContext(
            context_id=str(uuid.uuid4()),
            created_at=datetime.now(),
            manifest=manifest,
            state=RuntimeStateMachine(current=RuntimeState.BOOTSTRAP),
            configuration=RuntimeConfiguration.from_app_config(config),
            version=RuntimeVersion(current=manifest.runtime_version),
            machine_id=platform.node(),
        )
        
        logger.info(f"RuntimeContext created: {self._context.context_id}")
        return self._context
    
    def get_context(self) -> RuntimeContext:
        """Get current RuntimeContext."""
        if self._context is None:
            raise RuntimeError("RuntimeContext not initialized. Call create_context() first.")
        return self._context
    
    def update_state(self, new_state: RuntimeState) -> None:
        """Update runtime state."""
        context = self.get_context()
        old = context.state.current
        context.state.transition_to(new_state)
        logger.info(f"RuntimeState changed: {old.name} -> {new_state.name}")
    
    def update_session(self, session: RuntimeSession) -> None:
        """Update runtime session."""
        context = self.get_context()
        context.session = session
        logger.info(f"RuntimeSession updated: {session.session_id}")
    
    def update_version(self, new_version: int) -> None:
        """Update runtime version."""
        context = self.get_context()
        context.version.update_current(new_version)
        context.manifest.runtime_version = new_version
        logger.info(f"RuntimeVersion updated: {new_version}")
    
    def _load_manifest(self, paths) -> RuntimeManifest:
        """Load manifest from runtime root."""
        manifest_path = paths.runtime_root / "manifest.json"
        if manifest_path.exists():
            try:
                import json
                with open(manifest_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                return RuntimeManifest.from_dict(data)
            except Exception as e:
                logger.warning(f"Failed to load manifest: {e}")
        return RuntimeManifest()