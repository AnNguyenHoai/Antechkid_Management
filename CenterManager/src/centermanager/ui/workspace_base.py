# -*- coding: utf-8 -*-
"""WorkspaceBase - Base class for all workspaces with platform integration."""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget

from centermanager.platform.context import PlatformContext
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.business import WriteGuard, PermissionGuard

# Tạo metaclass kết hợp giữa QWidget và ABC
from abc import ABCMeta
QtABCMeta = type("QtABCMeta", (type(QWidget), ABCMeta), {})


class WorkspaceBase(QWidget, ABC, metaclass=QtABCMeta):
    """
    Base class for all workspaces.
    Provides platform integration and lifecycle.
    """

    # Signal emitted when workspace data changes
    data_changed = Signal()

    def __init__(
        self,
        workspace_id: str,
        platform_context: PlatformContext,
        collaboration_manager: CollaborationManager,
        parent: Optional[QWidget] = None,
    ):
        super().__init__(parent)
        self._workspace_id = workspace_id
        self._platform_context = platform_context
        self._collaboration_manager = collaboration_manager
        self._write_guard = WriteGuard(collaboration_manager)
        self._permission_guard = PermissionGuard(collaboration_manager, platform_context)

        self._is_active = False
        self._is_initialized = False

    @abstractmethod
    def initialize(self) -> None:
        """Initialize workspace content and register event listeners."""
        pass

    @abstractmethod
    def refresh(self) -> None:
        """Refresh workspace data."""
        pass

    def start(self) -> None:
        """Called when platform enters RUNNING state."""
        pass

    def stop(self) -> None:
        """Called when platform enters STOPPING state."""
        pass

    def dispose(self) -> None:
        """Release resources, unregister event listeners."""
        pass

    def activate(self) -> None:
        """Called when workspace becomes active."""
        self._is_active = True

    def deactivate(self) -> None:
        """Called when workspace becomes inactive."""
        self._is_active = False

    def can_write(self) -> bool:
        """Check if write is allowed."""
        return self._write_guard.can_write()

    def require_write(self) -> None:
        """Require write permission."""
        self._write_guard.require_write()

    def require_permission(self, permission: str) -> None:
        """Require a specific business permission."""
        self._permission_guard.require_read(permission)

    def on_data_changed(self) -> None:
        """Emit data_changed signal."""
        self.data_changed.emit()

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    @property
    def is_active(self) -> bool:
        return self._is_active

    @property
    def is_initialized(self) -> bool:
        return self._is_initialized