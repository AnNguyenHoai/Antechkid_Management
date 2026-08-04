# -*- coding: utf-8 -*-
import logging
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QStackedWidget
from PySide6.QtCore import Qt

from centermanager.ui.home import HomePage
from centermanager.ui.student_workspace import StudentWorkspaceShell
from centermanager.services.permission_service import PermissionService
from centermanager.core.current_user import get_current_user
from centermanager.ui.permission_helpers import UIPermissionHelper
from centermanager.ui.teacher_workspace.teacher_workspace_shell import TeacherWorkspaceShell
from centermanager.ui.class_workspace.class_workspace_shell import ClassWorkspaceShell
from centermanager.ui.finance_workspace import FinanceWorkspaceShell

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
        class_service,
        class_timeline_service,
        teacher_assignment_service_for_class,
        permission_service: PermissionService,
        finance_service,
        income_service,
        expense_service,
        finance_dashboard_service,
        outstanding_service,
        attendance_service,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)

        # Lưu tất cả services
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
        self._teacher_service = teacher_service
        self._teacher_assignment_service = teacher_assignment_service
        self._teacher_document_service = teacher_document_service
        self._teacher_timeline_service = teacher_timeline_service
        self._class_service = class_service
        self._class_timeline_service = class_timeline_service
        self._teacher_assignment_service_for_class = teacher_assignment_service_for_class
        self._permission_service = permission_service
        self._finance_service = finance_service
        self._income_service = income_service
        self._expense_service = expense_service
        self._finance_dashboard_service = finance_dashboard_service
        self._outstanding_service = outstanding_service
        self._attendance_service = attendance_service

        self._permission_helper = UIPermissionHelper(permission_service._session_factory)

        self.setWindowTitle("CenterManager")
        self.setMinimumSize(1000, 700)

        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)

        self._current_user = get_current_user()
        self._role_name = self._current_user.role.name if self._current_user and self._current_user.role else None

        # Home
        self.home_page = HomePage(home_service=self._home_service, parent=self)
        self.home_page.workspace_selected.connect(self._on_workspace_selected)
        self.central_stack.addWidget(self.home_page)

        # Student Workspace
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
            income_service=self._income_service,
            class_service=self._class_service,
            permission_service=self._permission_service,
            outstanding_service=self._outstanding_service,
            attendance_service=self._attendance_service,
        )
        self.student_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.student_workspace)
        self.student_workspace.go_to_finance.connect(self._on_go_to_finance)

        # Teacher Workspace
        self.teacher_workspace = TeacherWorkspaceShell(
            teacher_service=self._teacher_service,
            assignment_service=self._teacher_assignment_service,
            document_service=self._teacher_document_service,
            timeline_service=self._teacher_timeline_service,
        )
        self.teacher_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.teacher_workspace)

        # Class Workspace
        self.class_workspace = ClassWorkspaceShell(
            class_service=self._class_service,
            assignment_service=self._teacher_assignment_service_for_class,
            timeline_service=self._class_timeline_service,
            session_service=self._session_service,
            note_service=self._note_service,
            highlight_service=self._highlight_service,
            student_service=self._student_service,
            attendance_service=self._attendance_service,
        )
        self.class_workspace.go_home.connect(self._go_home)
        self.class_workspace.attendance_updated.connect(self._on_attendance_updated)
        self.central_stack.addWidget(self.class_workspace)

        # Finance Workspace
        self.finance_workspace = FinanceWorkspaceShell(
            income_service=self._income_service,
            student_service=self._student_service,
            class_service=self._class_service,
            expense_service=self._expense_service,
            dashboard_service=self._finance_dashboard_service,
            outstanding_service=self._outstanding_service,
        )
        self.finance_workspace.go_home.connect(self._go_home)
        self.student_workspace.go_to_finance.connect(self._on_go_to_finance)
        self.central_stack.addWidget(self.finance_workspace)

        self.central_stack.setCurrentWidget(self.home_page)
        self.statusBar().showMessage(f"Welcome, {self._current_user.full_name if self._current_user else 'User'}")

        self._apply_menu_permissions()
        self._refresh_student_list()

    def _apply_menu_permissions(self) -> None:
        self.home_page.refresh()

    def _on_workspace_selected(self, workspace_id: str) -> None:
        permission_map = {
            "student": None,
            "teacher": "teacher.view",
            "class": "class.view",
            "finance": "finance.view",
            "reports": "report.view",
            "settings": "setting.update",
        }

        required_perm = permission_map.get(workspace_id)
        if required_perm:
            if not self._permission_helper.has_permission(required_perm):
                self.statusBar().showMessage(f"Permission denied: Insufficient access rights for {workspace_id}")
                logger.warning(f"Permission denied for {workspace_id}")
                return

        if workspace_id == "student":
            self.central_stack.setCurrentWidget(self.student_workspace)
            if self.student_workspace.current_student_id is not None:
                self.student_workspace.show_student(self.student_workspace.current_student_id)
            else:
                self.student_workspace.navigate_to("dashboard")
            self.statusBar().showMessage("Student Workspace")
            self._refresh_student_list()
            self.student_workspace.dashboard_page.refresh()
        elif workspace_id == "teacher":
            self.central_stack.setCurrentWidget(self.teacher_workspace)
            self.teacher_workspace.navigate_to("dashboard")
            self.statusBar().showMessage("Teacher Workspace")
        elif workspace_id == "class":
            self.central_stack.setCurrentWidget(self.class_workspace)
            self.class_workspace.navigate_to("dashboard")
            self.statusBar().showMessage("Class Workspace")
        elif workspace_id == "finance":
            self.central_stack.setCurrentWidget(self.finance_workspace)
            self.finance_workspace.navigate_to("dashboard")
            self.statusBar().showMessage("Finance Workspace")
        elif workspace_id == "reports":
            self.statusBar().showMessage("Reports Workspace coming soon")
        elif workspace_id == "settings":
            self.statusBar().showMessage("Settings coming soon")
        else:
            self.statusBar().showMessage(f"Workspace {workspace_id} not available")

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

    def _on_attendance_updated(self) -> None:
        self.student_workspace.refresh_current_student()

    def _on_go_to_finance(self) -> None:
        self._on_workspace_selected("finance")