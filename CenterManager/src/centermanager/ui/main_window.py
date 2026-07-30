# -*- coding: utf-8 -*-
import logging
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QStackedWidget
from PySide6.QtCore import Qt

from centermanager.ui.home import HomePage
from centermanager.ui.student_workspace import StudentWorkspaceShell
from centermanager.services.permission_service import PermissionService
from centermanager.core.current_user import get_current_user
from centermanager.ui.permission_helpers import UIPermissionHelper, get_menu_items_for_role
from centermanager.ui.teacher_workspace.teacher_workspace_shell import TeacherWorkspaceShell


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
        student_note_service,
        document_service,
        analytics_service,
        filter_service,
        export_service,
        import_service,
        teacher_service,
        teacher_assignment_service,
        teacher_document_service,
        teacher_timeline_service,
        permission_service: PermissionService,
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
        self._analytics_service = analytics_service
        self._filter_service = filter_service
        self._export_service = export_service
        self._import_service = import_service
        self._permission_service = permission_service
        self._permission_helper = UIPermissionHelper(permission_service._session_factory)

        self.setWindowTitle("CenterManager")
        self.setMinimumSize(1000, 700)

        # Central stacked widget
        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)

        # Get current user for menu filtering
        self._current_user = get_current_user()
        self._role_name = self._current_user.role.name if self._current_user and self._current_user.role else None

        # Home Page
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
            analytics_service=self._analytics_service,
            filter_service=self._filter_service,
            export_service=self._export_service,
            import_service=self._import_service,
        )
        self.student_workspace.go_home.connect(self._go_home)

        self.central_stack.addWidget(self.student_workspace)
        self.teacher_workspace = TeacherWorkspaceShell(
            teacher_service=teacher_service,
            assignment_service=teacher_assignment_service,
            document_service=teacher_document_service,
            timeline_service=teacher_timeline_service,
        )
        self.teacher_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.teacher_workspace)
        
        # Initially show Home
        self.central_stack.setCurrentWidget(self.home_page)
        self.statusBar().showMessage(f"Welcome, {self._current_user.full_name if self._current_user else 'User'}")

        # Apply permission-based menu visibility
        self._apply_menu_permissions()

        self._refresh_student_list()

    def _apply_menu_permissions(self) -> None:
        """
        Apply permission-based visibility to menu items.
        This will be called after the UI is fully constructed.
        """
        # Get visible menu items for current role
        visible_items = get_menu_items_for_role(self._role_name)
        visible_ids = {item["id"] for item in visible_items}

        # Filter workspace cards on home page
        # The home page will be refreshed with only visible workspaces
        self.home_page.refresh()

        # Note: The actual workspace cards filtering is done in HomePage._populate_workspace_cards()
        # which uses the permission service

    def _on_workspace_selected(self, workspace_id: str) -> None:
        """Handle workspace selection from Home page."""
        # Check permission for workspace access
        permission_map = {
            "student": None,  # Always accessible
            "teacher": "teacher.view",
            "finance": "finance.view",
            "reports": "report.view",
            "settings": "setting.update",
        }

        required_perm = permission_map.get(workspace_id)
        if required_perm:
            if not self._permission_helper.has_permission(required_perm):
                self.statusBar().showMessage("Permission denied: Insufficient access rights")
                return

        if workspace_id == "student":
            self.central_stack.setCurrentWidget(self.student_workspace)
            self.statusBar().showMessage("Student Workspace")
            self._refresh_student_list()
            self.student_workspace.dashboard_page.refresh()
        elif workspace_id == "teacher":
            self.central_stack.setCurrentWidget(self.teacher_workspace)
            self.statusBar().showMessage("Teacher Workspace")
            self.teacher_workspace.list_page.refresh()
        elif workspace_id == "finance":
            self.statusBar().showMessage("Finance Workspace coming soon")
        elif workspace_id == "reports":
            self.statusBar().showMessage("Reports Workspace coming soon")
        elif workspace_id == "settings":
            self.statusBar().showMessage("Settings coming soon")
        else:
            self.statusBar().showMessage(f"Workspace {workspace_id} not available")

    def _go_home(self) -> None:
        """Navigate back to Home."""
        self.central_stack.setCurrentWidget(self.home_page)
        self.home_page.refresh()
        self.statusBar().showMessage("Home")

    def _refresh_student_list(self) -> None:
        """Refresh student list in the student workspace."""
        try:
            students = self._student_service.list_students()
            self.student_workspace.list_page._students = students
            self.student_workspace.list_page.refresh()
        except Exception as e:
            logger.exception("Failed to refresh student list")