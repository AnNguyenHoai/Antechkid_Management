# -*- coding: utf-8 -*-
"""
MainWindow – container for Home page and Workspaces.
"""
import logging
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QStatusBar
from PySide6.QtCore import Qt

from centermanager.ui.home import HomePage  # nếu bạn đã tạo ui/home/HomePage
# hoặc nếu vẫn dùng file cũ: from centermanager.ui.home_page import HomePage
from centermanager.ui.student_workspace import StudentWorkspaceShell

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
        )
        self.student_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.student_workspace)

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