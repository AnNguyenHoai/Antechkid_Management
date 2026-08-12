# -*- coding: utf-8 -*-
"""Workspace registration helpers."""

from dataclasses import dataclass
from typing import Type, Callable, Optional, Any


@dataclass
class WorkspaceRegistration:
    """Registration info for a workspace."""
    workspace_id: str
    name: str
    icon: str
    description: str
    factory: Callable[[], Any]
    permission_required: Optional[str] = None
    order: int = 0

    def to_descriptor(self):
        """Convert to WorkspaceDescriptor."""
        from centermanager.platform.workspace import WorkspaceDescriptor
        return WorkspaceDescriptor(
            workspace_id=self.workspace_id,
            name=self.name,
            icon=self.icon,
            description=self.description,
            factory=self.factory,
            permission_required=self.permission_required,
            order=self.order,
        )