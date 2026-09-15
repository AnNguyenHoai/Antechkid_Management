# -*- coding: utf-8 -*-
"""RuntimeManifest - Single source of truth for runtime description."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class RuntimeManifest:
    """Runtime description - loaded from manifest.json."""
    
    schema_version: int = 1
    runtime_version: int = 0
    database_version: int = 0
    minimum_app_version: str = "0.1.0"
    publisher: str = "CenterManager"
    branch: str = "main"
    created_at: datetime = field(default_factory=datetime.now)
    published_at: Optional[datetime] = None
    
    def get_version(self) -> int:
        """Get current runtime version."""
        return self.runtime_version
    
    def is_compatible(self, app_version: str) -> bool:
        """Check if runtime is compatible with app version."""
        # Simple version check - can be enhanced later
        return True
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "schema_version": self.schema_version,
            "runtime_version": self.runtime_version,
            "database_version": self.database_version,
            "minimum_app_version": self.minimum_app_version,
            "publisher": self.publisher,
            "branch": self.branch,
            "created_at": self.created_at.isoformat(),
            "published_at": self.published_at.isoformat() if self.published_at else None,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "RuntimeManifest":
        """Create from dictionary."""
        return cls(
            schema_version=data.get("schema_version", 1),
            runtime_version=data.get("runtime_version", 0),
            database_version=data.get("database_version", 0),
            minimum_app_version=data.get("minimum_app_version", "0.1.0"),
            publisher=data.get("publisher", "CenterManager"),
            branch=data.get("branch", "main"),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            published_at=datetime.fromisoformat(data["published_at"]) if data.get("published_at") else None,
        )