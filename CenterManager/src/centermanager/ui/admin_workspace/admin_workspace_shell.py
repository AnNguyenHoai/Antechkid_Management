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
from centermanager.ui.diagnostics_page import DiagnosticsPage


class AdminWorkspaceShell(QWidget):
    go_home = Signal()

    def __init__(
        self,
        permission_service,
        platform_context=None,          # <-- THÊM
        collaboration_manager=None,     # <-- THÊM
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._permission_service = permission_service
        self._platform_context = platform_context
        self._collaboration_manager = collaboration_manager

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
            {"id": "diagnostics", "icon": "🔍", "label": "Diagnostics"},
        ]
        self.nav = WorkspaceNavigation("Admin Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        self.users_page = UserListPage(
            self._permission_service,
            self._collaboration_manager,
            None,  # notification_service placeholder
        )
        self.content_stack.addWidget(self.users_page)

        self.settings_page = SettingsPage(
            self._collaboration_manager,
            None,  # notification_service placeholder
        )
        self.content_stack.addWidget(self.settings_page)

        self.diagnostics_page = DiagnosticsPage(
            self._collaboration_manager,
        )
        self.content_stack.addWidget(self.diagnostics_page)

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
        elif page_id == "diagnostics":
            self.content_stack.setCurrentWidget(self.diagnostics_page)
            self.nav.set_active_page("diagnostics")
            self.header.set_context("Admin Workspace", "Diagnostics")
            self.diagnostics_page.refresh()

    def set_write_enabled(self, enabled: bool) -> None:
        if hasattr(self.users_page, 'set_write_enabled'):
            self.users_page.set_write_enabled(enabled)
        if hasattr(self.settings_page, 'set_write_enabled'):
            self.settings_page.set_write_enabled(enabled)