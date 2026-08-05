# -*- coding: utf-8 -*-
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QFrame, QSizePolicy
)

from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.admin_workspace.user_list_page import UserListPage
from centermanager.ui.admin_workspace.settings_page import SettingsPage
from centermanager.services.permission_service import PermissionService
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService


class AdminWorkspaceShell(QWidget):
    go_home = Signal()

    def __init__(
        self,
        permission_service: PermissionService,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._permission_service = permission_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service

        self._setup_ui()
        self._connect_signals()
        self.navigate_to("users")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = WorkspaceHeader("Admin Workspace", "Users")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        pages = [
            {"id": "users", "icon": "👤", "label": "Users"},
            {"id": "settings", "icon": "⚙️", "label": "Settings"},
        ]
        self.nav = WorkspaceNavigation("Admin Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        self.users_page = UserListPage(
            self._permission_service,
            self._collaboration_manager,
            self._notification_service,
        )
        self.content_stack.addWidget(self.users_page)

        # ===== SỬA LỖI TẠI ĐÂY: thêm 2 tham số =====
        self.settings_page = SettingsPage(
            self._collaboration_manager,
            self._notification_service,
        )
        self.content_stack.addWidget(self.settings_page)

        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

    def _connect_signals(self) -> None:
        self.nav.page_selected.connect(self.navigate_to)
        self.header.back_home_clicked.connect(self.go_home.emit)

    def navigate_to(self, page_id: str) -> None:
        if page_id == "users":
            self.content_stack.setCurrentWidget(self.users_page)
            self.nav.set_active_page("users")
            self.header.set_context("Admin Workspace", "Users")
            self.users_page.refresh()
        elif page_id == "settings":
            self.content_stack.setCurrentWidget(self.settings_page)
            self.nav.set_active_page("settings")
            self.header.set_context("Admin Workspace", "Settings")

    def set_write_enabled(self, enabled: bool) -> None:
        if hasattr(self.users_page, 'set_write_enabled'):
            self.users_page.set_write_enabled(enabled)
        # Cập nhật cho SettingsPage
        if hasattr(self.settings_page, 'set_write_enabled'):
            self.settings_page.set_write_enabled(enabled)