# -*- coding: utf-8 -*-
import logging
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget, QHBoxLayout, QLabel, QPushButton, QMessageBox
from PySide6.QtCore import Qt

from centermanager.ui.home import HomePage
from centermanager.ui.student_workspace import StudentWorkspaceShell
from centermanager.services.permission_service import PermissionService
from centermanager.core.current_user import get_current_user
from centermanager.ui.permission_helpers import UIPermissionHelper
from centermanager.ui.teacher_workspace.teacher_workspace_shell import TeacherWorkspaceShell
from centermanager.ui.class_workspace.class_workspace_shell import ClassWorkspaceShell
from centermanager.ui.finance_workspace import FinanceWorkspaceShell
from centermanager.ui.admin_workspace import AdminWorkspaceShell

# NEW imports for collaboration
from centermanager.platform.collaboration import CollaborationManager, CollaborationMode
from centermanager.platform.notification import NotificationService
from centermanager.events.collaboration_events import ModeChanged, WriteGranted, WriteReleased

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
        income_service,
        expense_service,
        finance_dashboard_service,
        outstanding_service,
        attendance_service,
        report_service,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
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
        self._teacher_service = teacher_service
        self._teacher_assignment_service = teacher_assignment_service
        self._teacher_document_service = teacher_document_service
        self._teacher_timeline_service = teacher_timeline_service
        self._class_service = class_service
        self._class_timeline_service = class_timeline_service
        self._teacher_assignment_service_for_class = teacher_assignment_service_for_class
        self._permission_service = permission_service
        self._income_service = income_service
        self._expense_service = expense_service
        self._finance_dashboard_service = finance_dashboard_service
        self._outstanding_service = outstanding_service
        self._attendance_service = attendance_service
        self._report_service = report_service

        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service

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
            report_service=self._report_service,
            collaboration_manager=self._collaboration_manager,
            notification_service=self._notification_service,
        )
        self.student_workspace.go_home.connect(self._go_home)
        self.student_workspace.go_to_finance.connect(self._on_go_to_finance)
        self.central_stack.addWidget(self.student_workspace)

        # Teacher Workspace
        self.teacher_workspace = TeacherWorkspaceShell(
            teacher_service=self._teacher_service,
            assignment_service=self._teacher_assignment_service,
            document_service=self._teacher_document_service,
            timeline_service=self._teacher_timeline_service,
            collaboration_manager=self._collaboration_manager,
            notification_service=self._notification_service,
        )
        self.teacher_workspace.go_home.connect(self._go_home)
        self.teacher_workspace.navigate_to_class.connect(self._on_navigate_to_class)
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
            collaboration_manager=self._collaboration_manager,
            notification_service=self._notification_service,
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
            collaboration_manager=self._collaboration_manager,
            notification_service=self._notification_service,
        )
        self.finance_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.finance_workspace)

        # Admin Workspace
        self.admin_workspace = AdminWorkspaceShell(
            permission_service=self._permission_service,
            collaboration_manager=self._collaboration_manager,
            notification_service=self._notification_service,
        )
        self.admin_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.admin_workspace)

        # Collaboration status bar
        self._setup_collaboration_status_bar()
        self._connect_collaboration_events()

        self.central_stack.setCurrentWidget(self.home_page)
        self.statusBar().showMessage(f"Welcome, {self._current_user.full_name if self._current_user else 'User'}")

        self._apply_menu_permissions()
        self._refresh_student_list()

        # Set initial write buttons state
        self._update_write_buttons(CollaborationMode.READ)
        self._update_write_actions(CollaborationMode.READ)

    def _setup_collaboration_status_bar(self) -> None:
        status_bar = self.statusBar()
        status_bar.clearMessage()

        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # Mode label
        self.mode_label = QLabel("Mode: READ")
        self.mode_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.mode_label)

        # User label
        current_user = get_current_user()
        user_display = current_user.full_name if current_user else "Unknown"
        self.user_label = QLabel(f"User: {user_display}")
        layout.addWidget(self.user_label)

        # Version label
        version = self._collaboration_manager.get_version()
        self.version_label = QLabel(f"Version: {version}")
        layout.addWidget(self.version_label)

        # Deployment label
        profile = self._collaboration_manager.get_deployment_profile()
        self.deployment_label = QLabel(f"Deployment: {profile}")
        layout.addWidget(self.deployment_label)

        # Git Status label
        self.git_status_label = QLabel("Git: --")
        layout.addWidget(self.git_status_label)

        # Spacer
        layout.addStretch()

        # Request Write button
        self.write_btn = QPushButton("Request Write")
        self.write_btn.setFixedHeight(28)
        self.write_btn.clicked.connect(self._on_request_write)
        layout.addWidget(self.write_btn)

        # Release Write button (initially hidden)
        self.release_btn = QPushButton("Release Write")
        self.release_btn.setFixedHeight(28)
        self.release_btn.setVisible(False)
        self.release_btn.clicked.connect(self._on_release_write)
        layout.addWidget(self.release_btn)

        # Publish button
        self.publish_btn = QPushButton("Publish")
        self.publish_btn.setFixedHeight(28)
        self.publish_btn.setVisible(False)
        self.publish_btn.clicked.connect(self._on_publish)
        layout.addWidget(self.publish_btn)

        status_bar.addPermanentWidget(widget, 1)
        self._collab_status_widget = widget

        self._update_write_buttons(CollaborationMode.READ)
        self._update_git_status()

    def _update_git_status(self) -> None:
        status = self._collaboration_manager.synchronization_status()
        state = status.get("state", "OFFLINE")
        commit = status.get("commit", "")
        branch = status.get("branch", "")
        self.git_status_label.setText(f"Git: {state} ({branch} {commit})")

    def _on_publish(self) -> None:
        if self._collaboration_manager.current_mode() != CollaborationMode.WRITE:
            QMessageBox.warning(
                self,
                "Cannot Publish",
                "You must be in WRITE mode to publish.\n\n"
                "Click 'Request Write' first, then try again."
            )
            return

        if not self._collaboration_manager._sync_provider:
            QMessageBox.warning(self, "Publish", "Git synchronization is not configured.")
            logger.warning("Publish attempted but sync_provider is None.")
            return

        try:
            message = f"Publish by {get_current_user().full_name}"
            success = self._collaboration_manager.publish(message)
            if success:
                QMessageBox.information(self, "Publish", "Publish successful.")
                self._update_git_status()
            else:
                QMessageBox.warning(self, "Publish", "Publish failed. Please check logs for details.")
                logger.error("Publish returned False.")
        except Exception as e:
            logger.exception("Publish error")
            QMessageBox.critical(self, "Error", f"Publish error: {str(e)}")

    def _connect_collaboration_events(self) -> None:
        self._collaboration_manager._event_bus.register(ModeChanged, self._on_mode_changed)
        self._collaboration_manager._event_bus.register(WriteGranted, self._on_write_granted)
        self._collaboration_manager._event_bus.register(WriteReleased, self._on_write_released)

        # Notification listener
        self._notification_service.add_listener(self._on_notification)

    def _on_mode_changed(self, event: ModeChanged) -> None:
        mode = event.mode
        mode_str = mode.value if hasattr(mode, 'value') else str(mode)
        self.mode_label.setText(f"Mode: {mode_str}")
        self._update_write_buttons(mode)
        self._update_write_actions(mode)
        self._update_git_status()

    def _on_write_granted(self, event: WriteGranted) -> None:
        self._notification_service.notify(f"Write access granted to {event.owner}", "success")

    def _on_write_released(self, event: WriteReleased) -> None:
        self._notification_service.notify(f"Write access released by {event.owner}", "info")

    def _update_write_buttons(self, mode: CollaborationMode) -> None:
        is_write = (mode == CollaborationMode.WRITE)
        self.write_btn.setVisible(not is_write)
        self.release_btn.setVisible(is_write)
        self.publish_btn.setVisible(is_write)
        if is_write:
            session_info = self._collaboration_manager.get_session_info()
            self.write_btn.setToolTip(f"Current session: {session_info.get('session_id')}")
        else:
            self.write_btn.setToolTip("Request write access to edit data")

    def _on_request_write(self) -> None:
        try:
            success = self._collaboration_manager.request_write()
            if success:
                QMessageBox.information(self, "Write Request", "Write access granted.")
                self._on_mode_changed(ModeChanged(mode=CollaborationMode.WRITE))
            else:
                QMessageBox.warning(self, "Write Request", "Could not acquire write lock. Someone else is editing.")
                logger.warning("Request write failed")
        except Exception as e:
            logger.exception("Error requesting write")
            QMessageBox.critical(self, "Error", f"Request write error: {str(e)}")

    def _on_release_write(self) -> None:
        try:
            success = self._collaboration_manager.release_write()
            if success:
                QMessageBox.information(self, "Release Write", "Write access released.")
                self._on_mode_changed(ModeChanged(mode=CollaborationMode.READ))
            else:
                QMessageBox.warning(self, "Release Write", "Failed to release write lock.")
        except Exception as e:
            logger.exception("Error releasing write")
            QMessageBox.critical(self, "Error", f"Release write error: {str(e)}")

    def _on_notification(self, message: str, severity: str) -> None:
        self.statusBar().showMessage(message, 3000)

    def _update_write_actions(self, mode: CollaborationMode) -> None:
        is_write = (mode == CollaborationMode.WRITE)
        for i in range(self.central_stack.count()):
            widget = self.central_stack.widget(i)
            if hasattr(widget, 'set_write_enabled'):
                widget.set_write_enabled(is_write)

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
        elif workspace_id == "admin":
            self.central_stack.setCurrentWidget(self.admin_workspace)
            self.admin_workspace.navigate_to("users")
            self.statusBar().showMessage("Admin Workspace")
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

    def _on_navigate_to_class(self, class_id: int) -> None:
        self._on_workspace_selected("class")
        self.class_workspace.show_class(class_id)

    def closeEvent(self, event):
        if self._collaboration_manager.current_mode() == CollaborationMode.WRITE:
            logger.info("Releasing write lock on application close...")
            self._collaboration_manager.release_write()
        event.accept()