# -*- coding: utf-8 -*-
"""
AssessmentWorkspace - Shell for Assessment Workspace.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QFrame

from centermanager.services.assessment_service import AssessmentService
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.assessment.assessment_dashboard import AssessmentDashboard
from centermanager.ui.assessment.assessment_list_page import AssessmentListPage


class AssessmentWorkspace(QWidget):
    go_home = Signal()

    def __init__(
        self,
        assessment_service: AssessmentService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = assessment_service
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = WorkspaceHeader("Assessment Workspace", "Dashboard")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        pages = [
            {"id": "dashboard", "icon": "📊", "label": "Dashboard"},
            {"id": "assessments", "icon": "📋", "label": "Assessments"},
        ]
        self.nav = WorkspaceNavigation("Assessment Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        self.dashboard = AssessmentDashboard(self._service)
        self.content_stack.addWidget(self.dashboard)

        self.list_page = AssessmentListPage(self._service)
        self.content_stack.addWidget(self.list_page)

        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

        self.navigate_to("dashboard")

    def navigate_to(self, page_id: str) -> None:
        page_map = {"dashboard": 0, "assessments": 1}
        idx = page_map.get(page_id, 0)
        self.content_stack.setCurrentIndex(idx)
        self.nav.set_active_page(page_id)
        labels = {"dashboard": "Dashboard", "assessments": "Assessments"}
        self.header.set_context("Assessment Workspace", labels.get(page_id, ""))
        if page_id == "assessments":
            self.list_page.refresh()
        elif page_id == "dashboard":
            self.dashboard.refresh()