# -*- coding: utf-8 -*-
"""WorkspaceRegistry - Platform workspace registration."""

import logging
from typing import Dict, List, Optional, Type, Any, Callable

from .workspace_descriptor import WorkspaceDescriptor

logger = logging.getLogger(__name__)


class WorkspaceRegistry:
    """Manages workspace registration and lifecycle."""
    
    def __init__(self):
        self._descriptors: Dict[str, WorkspaceDescriptor] = {}
        self._instances: Dict[str, Any] = {}
    
    def register(self, descriptor: WorkspaceDescriptor) -> None:
        """Register a workspace."""
        if descriptor.workspace_id in self._descriptors:
            logger.warning(f"Workspace {descriptor.workspace_id} already registered, overwriting.")
        self._descriptors[descriptor.workspace_id] = descriptor
        logger.info(f"Registered workspace: {descriptor.workspace_id}")
    
    def get_descriptor(self, workspace_id: str) -> Optional[WorkspaceDescriptor]:
        """Get workspace descriptor."""
        return self._descriptors.get(workspace_id)
    
    def list_descriptors(self) -> List[WorkspaceDescriptor]:
        """List all registered workspace descriptors, sorted by order."""
        return sorted(self._descriptors.values(), key=lambda d: d.order)
    
    def create_workspace(self, workspace_id: str) -> Optional[Any]:
        """Create and cache a workspace instance."""
        desc = self.get_descriptor(workspace_id)
        if not desc:
            logger.error(f"Workspace {workspace_id} not registered.")
            return None
        try:
            instance = desc.factory()
            self._instances[workspace_id] = instance
            return instance
        except Exception as e:
            logger.exception(f"Failed to create workspace {workspace_id}: {e}")
            return None
    
    def get_workspace(self, workspace_id: str) -> Optional[Any]:
        """Get existing workspace instance."""
        return self._instances.get(workspace_id)
    
    def clear(self) -> None:
        """Clear all instances (on shutdown)."""
        self._instances.clear()