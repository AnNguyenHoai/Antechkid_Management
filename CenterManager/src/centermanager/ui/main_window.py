# -*- coding: utf-8 -*-
"""
MainWindow – container for Home page and Workspaces.
"""
import logging
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QStackedWidget
from PySide6.QtCore import Qt

from centermanager.ui.home import HomePage
from centermanager.ui.student_workspace import StudentWorkspaceShell

from centermanager.ui.assessment.assessment_workspace import AssessmentWorkspace
from centermanager.ui.timeline.timeline_workspace import TimelineWorkspace
from centermanager.ui.reports.reports_workspace import ReportsWorkspace


logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(
        self,
        student_service,
        parent_service,
        timeline_service,
        assessment_service,
        summary_service,
        session_service,
        note_service,
        highlight_service,
        dashboard_service,
        home_service,
        student_note_service,   # thêm
        document_service,       # thêm
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._student_service = student_service
        self._parent_service = parent_service
        self._timeline_service = timeline_service
        self._assessment_service = assessment_service
        self._summary_service = summary_service
        self._session_service = session_service
        self._note_service = note_service
        self._highlight_service = highlight_service
        self._dashboard_service = dashboard_service
        self._home_service = home_service
        self._student_note_service = student_note_service
        self._document_service = document_service

        self.setWindowTitle("CenterManager")
        self.setMinimumSize(1000, 700)

        # Central stacked widget
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)

        # Home Page (Command Center)
        self.home_page = HomePage(home_service=self._home_service, parent=self)
        self.home_page.workspace_selected.connect(self._on_workspace_selected)
        self.central_stack.addWidget(self.home_page)

        # Student Workspace Shell
        self.student_workspace = StudentWorkspaceShell(
            student_service=self._student_service,
            parent_service=self._parent_service,
            timeline_service=self._timeline_service,
            assessment_service=self._assessment_service,
            summary_service=self._summary_service,
            session_service=self._session_service,
            note_service=self._note_service,
            highlight_service=self._highlight_service,
            dashboard_service=self._dashboard_service,
            student_note_service=self._student_note_service,
            document_service=self._document_service,
        )
        self.student_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.student_workspace)
        self.assessment_workspace = AssessmentWorkspace(assessment_service)
        self.assessment_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.assessment_workspace)

        self.timeline_workspace = TimelineWorkspace(timeline_service, student_service)
        self.timeline_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.timeline_workspace)

        self.reports_workspace = ReportsWorkspace(student_service, assessment_service)
        self.reports_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.reports_workspace)
        # Default: Home
        self.central_stack.setCurrentWidget(self.home_page)

        self.statusBar().showMessage("Ready")
        self._refresh_student_list()

    def _on_workspace_selected(self, workspace_id: str) -> None:
        if workspace_id == "student":
            self.central_stack.setCurrentWidget(self.student_workspace)
            self.statusBar().showMessage("Student Workspace")
            self._refresh_student_list()
            self.student_workspace.dashboard_page.refresh()
        elif workspace_id == "teacher":
            self.statusBar().showMessage("Teacher Workspace coming soon")
        elif workspace_id == "assessment":
            self.central_stack.setCurrentWidget(self.assessment_workspace)
            self.statusBar().showMessage("Assessment Workspace")
        elif workspace_id == "timeline":
            self.central_stack.setCurrentWidget(self.timeline_workspace)
            self.statusBar().showMessage("Timeline Workspace")
        elif workspace_id == "reports":
            self.central_stack.setCurrentWidget(self.reports_workspace)
            self.statusBar().showMessage("Reports Workspace")
        else:
            self.statusBar().showMessage(f"Workspace {workspace_id} not available yet")

    def _go_home(self) -> None:
        self.central_stack.setCurrentWidget(self.home_page)
        self.home_page.refresh()
        self.statusBar().showMessage("Home")

    def _refresh_student_list(self) -> None:
        try:
            students = self._student_service.list_students()
            self.student_workspace.list_page._students = students
            self.student_workspace.list_page.refresh()
        except Exception as e:
            logger.exception("Failed to refresh student list")