# -*- coding: utf-8 -*-
"""RuntimeContext - Single execution context for the Platform."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from .runtime_manifest import RuntimeManifest
from .runtime_state import RuntimeStateMachine
from .runtime_configuration import RuntimeConfiguration
from .runtime_session import RuntimeSession
from .runtime_version import RuntimeVersion


@dataclass
class RuntimeContext:
    """Single execution context for the Platform."""
    
    context_id: str
    created_at: datetime = field(default_factory=datetime.now)
    
    # Runtime components
    manifest: RuntimeManifest = field(default_factory=RuntimeManifest)
    state: RuntimeStateMachine = field(default_factory=RuntimeStateMachine)
    session: Optional[RuntimeSession] = None
    configuration: RuntimeConfiguration = field(default_factory=RuntimeConfiguration)
    version: RuntimeVersion = field(default_factory=RuntimeVersion)
    
    # Metadata
    correlation_id: Optional[str] = None
    machine_id: Optional[str] = None
    
    def is_ready(self) -> bool:
        """Check if platform is ready."""
        return self.state.is_ready()
    
    def can_write(self) -> bool:
        """Check if write mode is active."""
        if not self.session:
            return False
        return self.session.mode == "WRITE"
    
    def get_runtime_version(self) -> int:
        """Get current runtime version."""
        return self.manifest.runtime_version