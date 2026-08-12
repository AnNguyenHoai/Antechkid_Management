# -*- coding: utf-8 -*-
"""RuntimeContext - Platform runtime information."""

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from centermanager.platform.runtime.context.runtime_state import RuntimeStateMachine
from centermanager.platform.runtime.context.runtime_manifest import RuntimeManifest
from centermanager.platform.runtime.context.runtime_version import RuntimeVersion


@dataclass
class RuntimeContext:
    """Runtime execution information - Data Holder only."""
    
    context_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: datetime = field(default_factory=datetime.now)
    manifest: RuntimeManifest = field(default_factory=RuntimeManifest)
    state: RuntimeStateMachine = field(default_factory=RuntimeStateMachine)
    version: RuntimeVersion = field(default_factory=RuntimeVersion)
    machine_id: Optional[str] = None

    def get_runtime_version(self) -> int:
        return self.manifest.runtime_version

    def is_ready(self) -> bool:
        return self.state.is_ready()