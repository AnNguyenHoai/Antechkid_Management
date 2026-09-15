# -*- coding: utf-8 -*-
"""WorkspaceDescriptor - Module workspace registration."""

from dataclasses import dataclass, field
from typing import Optional, Callable, Type, List, Dict, Any


@dataclass
class WorkspaceDescriptor:
    """Describes a workspace for platform registration."""
    
    workspace_id: str
    name: str
    icon: str
    description: str
    factory: Callable[[], Any]  # Factory function to create workspace
    permission_required: Optional[str] = None
    order: int = 0
    capabilities: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_summary(self) -> dict:
        """Return summary for UI."""
        return {
            "id": self.workspace_id,
            "name": self.name,
            "icon": self.icon,
            "description": self.description,
            "permission_required": self.permission_required,
            "order": self.order,
        }