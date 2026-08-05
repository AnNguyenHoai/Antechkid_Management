# -*- coding: utf-8 -*-
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QFrame, QSizePolicy
)

from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.teacher_workspace.teacher_list_page import TeacherListPage
from centermanager.ui.teacher_workspace.teacher_detail_page import TeacherDetailPage
from centermanager.ui.teacher_workspace.teacher_dashboard_page import TeacherDashboardPage
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService


class TeacherWorkspaceShell(QWidget):
    go_home = Signal()
    navigate_to_class = Signal(int)

    def __init__(
        self,
        teacher_service,
        assignment_service,
        document_service,
        timeline_service,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._teacher_service = teacher_service
        self._assignment_service = assignment_service
        self._document_service = document_service
        self._timeline_service = timeline_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service

        self._current_teacher_id: Optional[int] = None

        self._setup_ui()
        self._connect_signals()
        self.navigate_to("dashboard")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = WorkspaceHeader("Teacher Workspace", "Dashboard")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        pages = [
            {"id": "dashboard", "icon": "📊", "label": "Dashboard"},
            {"id": "teachers", "icon": "👨‍🏫", "label": "Teachers"},
        ]
        self.nav = WorkspaceNavigation("Teacher Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        # Dashboard
        self.dashboard_page = TeacherDashboardPage(
            self._teacher_service,
            self._assignment_service,
            self._timeline_service
        )
        self.content_stack.addWidget(self.dashboard_page)

        # Teacher List
        self.list_page = TeacherListPage(
            self._teacher_service,
            self._assignment_service,
            self._document_service,
            self._timeline_service,
            self._collaboration_manager,
            self._notification_service,
        )
        self.list_page.teacher_selected.connect(self._on_teacher_selected)
        self.content_stack.addWidget(self.list_page)

        # Teacher Detail
        self.detail_page = TeacherDetailPage(
            self._teacher_service,
            self._assignment_service,
            self._document_service,
            self._timeline_service,
            self._collaboration_manager,
            self._notification_service,
        )
        self.detail_page.back_clicked.connect(self._on_back_from_detail)
        self.detail_page.teacher_updated.connect(self._on_teacher_updated)
        self.detail_page.class_clicked.connect(self.navigate_to_class.emit)
        self.content_stack.addWidget(self.detail_page)

        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

    def _connect_signals(self) -> None:
        self.nav.page_selected.connect(self.navigate_to)
        self.header.back_home_clicked.connect(self.go_home.emit)

    def navigate_to(self, page_id: str) -> None:
        if page_id == "dashboard":
            self.content_stack.setCurrentWidget(self.dashboard_page)
            self.nav.set_active_page("dashboard")
            self.header.set_context("Teacher Workspace", "Dashboard")
            self.dashboard_page.refresh()
        elif page_id == "teachers":
            self.content_stack.setCurrentWidget(self.list_page)
            self.nav.set_active_page("teachers")
            self.header.set_context("Teacher Workspace", "Teachers")
            self.list_page.refresh()

    def _on_teacher_selected(self, teacher_id: int) -> None:
        self._current_teacher_id = teacher_id
        self.detail_page.load_teacher(teacher_id)
        self.content_stack.setCurrentWidget(self.detail_page)
        self.nav.set_active_page("teachers")
        self.header.set_context("Teacher Workspace", "Teacher Detail")

    def _on_back_from_detail(self) -> None:
        self.navigate_to("teachers")
        self.list_page.refresh()

    def _on_teacher_updated(self) -> None:
        self.list_page.refresh()

    def set_write_enabled(self, enabled: bool) -> None:
        if hasattr(self.list_page, 'set_write_enabled'):
            self.list_page.set_write_enabled(enabled)
        if hasattr(self.detail_page, 'set_write_enabled'):
            self.detail_page.set_write_enabled(enabled)