# -*- coding: utf-8 -*-
"""UserContext - Current user information."""

from dataclasses import dataclass, field
from typing import Optional, Set


@dataclass
class UserContext:
    """Authenticated user information."""
    
    user_id: Optional[int] = None
    username: Optional[str] = None
    full_name: Optional[str] = None
    email: Optional[str] = None
    role: Optional[str] = None
    permissions: Set[str] = field(default_factory=set)
    is_admin: bool = False
    
    def has_permission(self, permission: str) -> bool:
        if self.is_admin:
            return True
        return permission in self.permissions