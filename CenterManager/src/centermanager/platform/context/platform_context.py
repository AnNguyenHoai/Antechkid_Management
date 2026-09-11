# -*- coding: utf-8 -*-
"""PlatformContext - Aggregated execution context for the Platform."""

from dataclasses import dataclass, field
from typing import Optional

from centermanager.models.user import User
from .runtime_context import RuntimeContext
from .deployment_context import DeploymentContext
from .session_context import SessionContext
from .workspace_context import WorkspaceContext
from .user_context import UserContext
from .configuration_context import ConfigurationContext


@dataclass
class PlatformContext:
    """
    Aggregated execution context for the Platform.
    All sub-contexts are independent and composed here.
    """
    runtime: RuntimeContext
    deployment: DeploymentContext
    session: SessionContext
    workspace: WorkspaceContext
    user: UserContext
    configuration: ConfigurationContext

    # Optional user reference (deprecated, use user context instead)
    current_user: Optional[User] = None

    @classmethod
    def create_default(cls) -> "PlatformContext":
        """Create a default PlatformContext with all sub-contexts initialized."""
        from .runtime_context import RuntimeContext
        from .deployment_context import DeploymentContext
        from .session_context import SessionContext
        from .workspace_context import WorkspaceContext
        from .user_context import UserContext
        from .configuration_context import ConfigurationContext

        return cls(
            runtime=RuntimeContext(),
            deployment=DeploymentContext(),
            session=SessionContext(),
            workspace=WorkspaceContext(),
            user=UserContext(),
            configuration=ConfigurationContext(),
        )