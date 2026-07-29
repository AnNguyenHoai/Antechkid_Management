# -*- coding: utf-8 -*-
"""
ReportsWorkspace - Shell for Reports Workspace.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QFrame

from centermanager.services.student_service import StudentService
from centermanager.services.assessment_service import AssessmentService
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.reports.reports_dashboard import ReportsDashboard


class ReportsWorkspace(QWidget):
    go_home = Signal()

    def __init__(
        self,
        student_service: StudentService,
        assessment_service: AssessmentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._student_service = student_service
        self._assessment_service = assessment_service
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = WorkspaceHeader("Reports Workspace", "Dashboard")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        pages = [
            {"id": "dashboard", "icon": "📊", "label": "Dashboard"},
        ]
        self.nav = WorkspaceNavigation("Reports Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        self.dashboard = ReportsDashboard(self._student_service, self._assessment_service)
        self.content_stack.addWidget(self.dashboard)

        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

        self.navigate_to("dashboard")

    def navigate_to(self, page_id: str) -> None:
        self.content_stack.setCurrentIndex(0)
        self.nav.set_active_page(page_id)
        self.header.set_context("Reports Workspace", "Dashboard")
        self.dashboard.refresh()