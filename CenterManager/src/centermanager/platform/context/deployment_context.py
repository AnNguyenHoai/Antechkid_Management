# -*- coding: utf-8 -*-
"""DeploymentContext - Deployment information."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class DeploymentContext:
    """Deployment configuration and state."""
    
    profile: str = "standalone"  # standalone, collaborative, server
    repository_url: Optional[str] = None
    branch: str = "main"
    local_path: Optional[str] = None
    git_configured: bool = False
    
    def is_collaborative(self) -> bool:
        return self.profile == "collaborative"
    
    def is_server(self) -> bool:
        return self.profile == "server"