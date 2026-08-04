# -*- coding: utf-8 -*-
"""
ClassWorkspaceShell - main shell for Class Workspace.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QFrame, QSizePolicy
)

from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.class_workspace.class_list_page import ClassListPage
from centermanager.ui.class_workspace.class_detail_page import ClassDetailPage
from centermanager.ui.class_workspace.class_dashboard_page import ClassDashboardPage


class ClassWorkspaceShell(QWidget):
    go_home = Signal()
    attendance_updated = Signal()

    def __init__(
        self,
        class_service,
        assignment_service,
        timeline_service,
        session_service,
        note_service,
        highlight_service,
        student_service,
        attendance_service,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._class_service = class_service
        self._assignment_service = assignment_service
        self._timeline_service = timeline_service
        self._session_service = session_service
        self._note_service = note_service
        self._highlight_service = highlight_service
        self._student_service = student_service
        self._attendance_service = attendance_service

        self._current_class_id: Optional[int] = None

        self._setup_ui()
        self._connect_signals()
        self.navigate_to("dashboard")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = WorkspaceHeader("Class Workspace", "Dashboard")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        pages = [
            {"id": "dashboard", "icon": "📊", "label": "Dashboard"},
            {"id": "classes", "icon": "📚", "label": "Classes"},
        ]
        self.nav = WorkspaceNavigation("Class Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        # Dashboard
        self.dashboard_page = ClassDashboardPage(
            self._class_service,
            self._session_service,
            self._timeline_service
        )
        self.content_stack.addWidget(self.dashboard_page)

        # Class List
        self.list_page = ClassListPage(
            self._class_service,
            self._assignment_service,
            self._timeline_service,
        )
        self.list_page.class_selected.connect(self._on_class_selected)
        self.content_stack.addWidget(self.list_page)

        # Class Detail
        self.detail_page = ClassDetailPage(
            class_service=self._class_service,
            assignment_service=self._assignment_service,
            timeline_service=self._timeline_service,
            session_service=self._session_service,
            note_service=self._note_service,
            highlight_service=self._highlight_service,
            student_service=self._student_service,
            attendance_service=self._attendance_service,
        )
        self.detail_page.back_clicked.connect(self._on_back_from_detail)
        self.detail_page.class_updated.connect(self._on_class_updated)
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
            self.header.set_context("Class Workspace", "Dashboard")
            self.dashboard_page.refresh()
        elif page_id == "classes":
            self.content_stack.setCurrentWidget(self.list_page)
            self.nav.set_active_page("classes")
            self.header.set_context("Class Workspace", "Classes")
            self.list_page.refresh()

    def _on_class_selected(self, class_id: int) -> None:
        self._current_class_id = class_id
        self.detail_page.load_class(class_id)
        self.content_stack.setCurrentWidget(self.detail_page)
        self.nav.set_active_page("classes")
        self.header.set_context("Class Workspace", "Class Detail")

    def _on_back_from_detail(self) -> None:
        self.navigate_to("classes")
        self.list_page.refresh()

    def _on_class_updated(self) -> None:
        self.list_page.refresh()
        self.attendance_updated.emit()