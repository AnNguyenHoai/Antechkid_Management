# -*- coding: utf-8 -*-
"""ModuleRegistry - Registers and manages workspace modules."""

from typing import Dict, List, Optional, Any
import logging

from .workspace_descriptor import WorkspaceDescriptor

logger = logging.getLogger(__name__)


class ModuleRegistry:
    """Registry for workspace modules."""
    
    def __init__(self):
        self._descriptors: Dict[str, WorkspaceDescriptor] = {}
        self._instances: Dict[str, Any] = {}
    
    def register(self, descriptor: WorkspaceDescriptor) -> None:
        """Register a workspace descriptor."""
        if descriptor.workspace_id in self._descriptors:
            logger.warning(f"Workspace {descriptor.workspace_id} already registered, overwriting")
        self._descriptors[descriptor.workspace_id] = descriptor
        logger.info(f"Registered workspace: {descriptor.workspace_id}")
    
    def get_descriptor(self, workspace_id: str) -> Optional[WorkspaceDescriptor]:
        """Get descriptor by ID."""
        return self._descriptors.get(workspace_id)
    
    def list_descriptors(self) -> List[WorkspaceDescriptor]:
        """List all registered descriptors."""
        return list(self._descriptors.values())
    
    def create_instance(self, workspace_id: str, **kwargs) -> Optional[Any]:
        """Create workspace instance from descriptor."""
        descriptor = self.get_descriptor(workspace_id)
        if not descriptor:
            logger.error(f"Workspace {workspace_id} not registered")
            return None
        
        try:
            instance = descriptor.factory()
            self._instances[workspace_id] = instance
            return instance
        except Exception as e:
            logger.exception(f"Failed to create workspace {workspace_id}: {e}")
            return None
    
    def get_instance(self, workspace_id: str) -> Optional[Any]:
        """Get existing workspace instance."""
        return self._instances.get(workspace_id)
    
    def clear(self) -> None:
        """Clear all instances."""
        self._instances.clear()