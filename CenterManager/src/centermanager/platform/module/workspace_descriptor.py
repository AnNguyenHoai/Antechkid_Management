# -*- coding: utf-8 -*-
"""WorkspaceDescriptor - Describes a workspace for registration."""

from dataclasses import dataclass
from typing import Optional, Callable, Type, Any


@dataclass
class WorkspaceDescriptor:
    """Descriptor for a workspace module."""
    
    workspace_id: str
    name: str
    icon: str
    description: str
    factory: Callable[[], Any]  # Factory function to create workspace
    permission: Optional[str] = None  # Required permission to access
    
    def __post_init__(self):
        """Validate descriptor."""
        if not self.workspace_id:
            raise ValueError("workspace_id is required")
        if not self.name:
            raise ValueError("name is required")
        if not self.factory:
            raise ValueError("factory is required")