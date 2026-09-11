# -*- coding: utf-8 -*-
"""WorkspaceContext - Current workspace information."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any


@dataclass
class WorkspaceContext:
    """Current workspace state."""
    
    active_workspace_id: Optional[str] = None
    active_workspace_name: Optional[str] = None
    active_page_id: Optional[str] = None
    navigation_history: list = field(default_factory=list)
    state: Dict[str, Any] = field(default_factory=dict)
    
    def set_active(self, workspace_id: str, name: str, page_id: str = "") -> None:
        self.active_workspace_id = workspace_id
        self.active_workspace_name = name
        self.active_page_id = page_id
        self.navigation_history.append({
            "workspace_id": workspace_id,
            "page_id": page_id,
            "timestamp": datetime.now()
        })
    
    def clear(self) -> None:
        self.active_workspace_id = None
        self.active_workspace_name = None
        self.active_page_id = None