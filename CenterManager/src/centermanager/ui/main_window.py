# -*- coding: utf-8 -*-
"""MainWindow - Application main window with platform integration."""

import logging
from typing import Optional

from PySide6.QtWidgets import QMainWindow, QStackedWidget, QWidget, QHBoxLayout, QLabel, QPushButton, QMessageBox
from PySide6.QtCore import Qt, QTimer

from centermanager.ui.home import HomePage
from centermanager.ui.student_workspace import StudentWorkspaceShell
from centermanager.ui.teacher_workspace.teacher_workspace_shell import TeacherWorkspaceShell
from centermanager.ui.class_workspace.class_workspace_shell import ClassWorkspaceShell
from centermanager.ui.finance_workspace import FinanceWorkspaceShell
from centermanager.ui.admin_workspace import AdminWorkspaceShell

from centermanager.services.permission_service import PermissionService
from centermanager.core.current_user import get_current_user
from centermanager.ui.permission_helpers import UIPermissionHelper

from centermanager.platform.context import PlatformContext
from centermanager.platform.collaboration import (
    CollaborationManager,
    CollaborationMode,
    ModeChanged,          # <-- Lấy từ đây
    SessionStarted,
    SessionEnded,
    WriteRequested,
    WriteGranted,
    WriteReleased,
    HeartbeatUpdated,
    QueueUpdated,
)
from centermanager.platform.sync import RuntimeSyncService
from centermanager.platform.business import BusinessModuleRegistry
from centermanager.events.synchronization_events import VersionUpdated
from centermanager.platform.sync.events import (
    UpdateDetected,
    SynchronizationDeferred,
    SynchronizationStarted as SyncStarted,
    SynchronizationCompleted,
    SynchronizationFailed,
    SyncStatusChanged,
)
logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    """Main application window with platform integration."""

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
        platform_context: PlatformContext,
        collaboration_manager: CollaborationManager,
        sync_service: RuntimeSyncService,
        module_registry: BusinessModuleRegistry,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)

        # Store services
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

        # Platform
        self._platform_context = platform_context
        self._collaboration_manager = collaboration_manager
        self._sync_service = sync_service
        self._module_registry = module_registry

        self._permission_helper = UIPermissionHelper(permission_service._session_factory)

        # UI Setup
        self.setWindowTitle("CenterManager")
        self.setMinimumSize(1000, 700)

        self.central_stack = QStackedWidget()
        self.setCentralWidget(self.central_stack)

        self._current_user = get_current_user()
        self._role_name = self._current_user.role.name if self._current_user and self._current_user.role else None

        # Setup pages
        self._setup_home()
        self._setup_student_workspace()
        self._setup_teacher_workspace()
        self._setup_class_workspace()
        self._setup_finance_workspace()
        self._setup_admin_workspace()

        # Collaboration status bar
        self._setup_collaboration_status_bar()
        self._connect_collaboration_events()

        # Start with home
        self.central_stack.setCurrentWidget(self.home_page)
        self.statusBar().showMessage(f"Welcome, {self._current_user.full_name if self._current_user else 'User'}")

        self._apply_menu_permissions()
        self._refresh_student_list()

        self._update_write_buttons(CollaborationMode.READ)
        self._update_write_actions(CollaborationMode.READ)

    # ===== Setup Methods =====

    def _setup_home(self) -> None:
        """Setup home page."""
        self.home_page = HomePage(home_service=self._home_service, parent=self)
        self.home_page.workspace_selected.connect(self._on_workspace_selected)
        self.central_stack.addWidget(self.home_page)

    def _setup_student_workspace(self) -> None:
        """Setup student workspace."""
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
            platform_context=self._platform_context,
            collaboration_manager=self._collaboration_manager,
        )
        self.student_workspace.go_home.connect(self._go_home)
        self.student_workspace.go_to_finance.connect(self._on_go_to_finance)
        self.central_stack.addWidget(self.student_workspace)
        # Khởi tạo workspace
        self.student_workspace.initialize()
        self.student_workspace.start()

    def _setup_teacher_workspace(self) -> None:
        """Setup teacher workspace."""
        self.teacher_workspace = TeacherWorkspaceShell(
            teacher_service=self._teacher_service,
            assignment_service=self._teacher_assignment_service,
            document_service=self._teacher_document_service,
            timeline_service=self._teacher_timeline_service,
            platform_context=self._platform_context,
            collaboration_manager=self._collaboration_manager,
        )
        self.teacher_workspace.go_home.connect(self._go_home)
        self.teacher_workspace.navigate_to_class.connect(self._on_navigate_to_class)
        self.central_stack.addWidget(self.teacher_workspace)

    def _setup_class_workspace(self) -> None:
        """Setup class workspace."""
        self.class_workspace = ClassWorkspaceShell(
            class_service=self._class_service,
            assignment_service=self._teacher_assignment_service_for_class,
            timeline_service=self._class_timeline_service,
            session_service=self._session_service,
            note_service=self._note_service,
            highlight_service=self._highlight_service,
            student_service=self._student_service,
            attendance_service=self._attendance_service,
            platform_context=self._platform_context,
            collaboration_manager=self._collaboration_manager,
        )
        self.class_workspace.go_home.connect(self._go_home)
        self.class_workspace.attendance_updated.connect(self._on_attendance_updated)
        self.central_stack.addWidget(self.class_workspace)

    def _setup_finance_workspace(self) -> None:
        """Setup finance workspace."""
        self.finance_workspace = FinanceWorkspaceShell(
            income_service=self._income_service,
            student_service=self._student_service,
            class_service=self._class_service,
            expense_service=self._expense_service,
            dashboard_service=self._finance_dashboard_service,
            outstanding_service=self._outstanding_service,
            platform_context=self._platform_context,
            collaboration_manager=self._collaboration_manager,
        )
        self.finance_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.finance_workspace)

    def _setup_admin_workspace(self) -> None:
        """Setup admin workspace."""
        self.admin_workspace = AdminWorkspaceShell(
            permission_service=self._permission_service,
            platform_context=self._platform_context,
            collaboration_manager=self._collaboration_manager,
        )
        self.admin_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.admin_workspace)

    # ===== Collaboration Status Bar =====

    def _setup_collaboration_status_bar(self) -> None:
        """Setup collaboration status bar with platform info."""
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

        # Runtime version label
        version = self._platform_context.runtime.manifest.runtime_version
        self.version_label = QLabel(f"Runtime: v{version}")
        layout.addWidget(self.version_label)

        # Sync status label
        sync_state = self._sync_service.current_state()
        status_text = sync_state.get("status", "idle")
        self.sync_label = QLabel(f"Sync: {status_text}")
        layout.addWidget(self.sync_label)

        # Queue label
        self.queue_label = QLabel("Queue: 0")
        layout.addWidget(self.queue_label)

        # Spacer
        layout.addStretch()

        # Request Write button
        self.write_btn = QPushButton("Request Write")
        self.write_btn.setFixedHeight(28)
        self.write_btn.clicked.connect(self._on_request_write)
        layout.addWidget(self.write_btn)

        # Release Write button
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
        self._update_queue_status()

    def _update_write_buttons(self, mode: CollaborationMode) -> None:
        """Update write button visibility based on mode."""
        is_write = (mode == CollaborationMode.WRITE)
        self.write_btn.setVisible(not is_write)
        self.release_btn.setVisible(is_write)
        self.publish_btn.setVisible(is_write)

        if is_write:
            session_info = self._collaboration_manager.get_session()
            if session_info:
                self.write_btn.setToolTip(f"Current session: {session_info.session_id}")
        else:
            self.write_btn.setToolTip("Request write access to edit data")

    def _update_git_status(self) -> None:
        """Update Git status on status bar."""
        # Currently not implemented for simplicity
        pass

    def _update_queue_status(self) -> None:
        """Update queue status on status bar."""
        try:
            queue_info = self._collaboration_manager.get_queue()
            length = queue_info.get("length", 0)
            self.queue_label.setText(f"Queue: {length}")
        except Exception:
            self.queue_label.setText("Queue: --")

    # ===== Collaboration Event Handling =====

    def _connect_collaboration_events(self) -> None:
        """Connect collaboration events."""
        self._collaboration_manager._event_bus.register(ModeChanged, self._on_mode_changed)   # <-- THÊM DÒNG NÀY
        self._collaboration_manager._event_bus.register(WriteGranted, self._on_write_granted)
        self._collaboration_manager._event_bus.register(WriteReleased, self._on_write_released)
        self._collaboration_manager._event_bus.register(QueueUpdated, self._on_queue_updated)

        # Sync events
        self._sync_service._event_bus.register(SyncStatusChanged, self._on_sync_status_changed)
        self._sync_service._event_bus.register(UpdateDetected, self._on_update_detected)
        self._sync_service._event_bus.register(SynchronizationCompleted, self._on_sync_completed)

        # Version updates
        self._collaboration_manager._event_bus.register(VersionUpdated, self._on_version_updated)

    def _on_mode_changed(self, event: ModeChanged) -> None:
        """Handle mode changed event."""
        mode_str = event.mode if isinstance(event.mode, str) else event.mode.value
        self.mode_label.setText(f"Mode: {mode_str}")
        mode = CollaborationMode.WRITE if mode_str == "WRITE" else CollaborationMode.READ
        self._update_write_buttons(mode)
        self._update_write_actions(mode)
        self._update_queue_status()

    def _on_write_granted(self, event: WriteGranted) -> None:
        """Handle write granted event."""
        self.statusBar().showMessage(f"Write access granted to {event.username}", 3000)

    def _on_write_released(self, event: WriteReleased) -> None:
        """Handle write released event."""
        self.statusBar().showMessage(f"Write access released by {event.username}", 3000)
        self._update_queue_status()

    def _on_queue_updated(self, event: QueueUpdated) -> None:
        """Handle queue updated event."""
        self._update_queue_status()
        if event.next_writer:
            self.statusBar().showMessage(f"Next writer: {event.next_writer}", 2000)

    def _on_sync_status_changed(self, event: SyncStatusChanged) -> None:
        """Handle sync status changed event."""
        self.sync_label.setText(f"Sync: {event.new_status}")
        if event.new_status == "failed":
            self.statusBar().showMessage("Synchronization failed. Check logs.", 3000)

    def _on_update_detected(self, event: UpdateDetected) -> None:
        """Handle update detected event."""
        self.statusBar().showMessage(
            f"Runtime update available: v{event.current_version} → v{event.remote_version}",
            5000,
        )

    def _on_sync_completed(self, event: SynchronizationCompleted) -> None:
        """Handle sync completed event."""
        self.statusBar().showMessage(
            f"Runtime updated to v{event.new_version}",
            3000,
        )
        self.version_label.setText(f"Runtime: v{event.new_version}")

    def _on_version_updated(self, event) -> None:
        """Handle version updated event."""
        # Refresh workspace if needed
        if self.central_stack.currentWidget() == self.student_workspace:
            self.student_workspace.refresh()
        self.version_label.setText(f"Runtime: v{event.new_version}")

    # ===== Write Actions =====

    def _update_write_actions(self, mode: CollaborationMode) -> None:
        """Update write actions for all workspaces."""
        is_write = (mode == CollaborationMode.WRITE)
        for i in range(self.central_stack.count()):
            widget = self.central_stack.widget(i)
            if hasattr(widget, 'set_write_enabled'):
                widget.set_write_enabled(is_write)

    def _on_request_write(self) -> None:
        """Handle request write button click."""
        try:
            reason = "Manual request"
            success = self._collaboration_manager.request_write(reason=reason)
            if success:
                self.statusBar().showMessage("Write access granted.", 3000)
            else:
                self.statusBar().showMessage("Write request queued.", 3000)
                self._update_queue_status()
        except Exception as e:
            logger.exception("Error requesting write")
            QMessageBox.critical(self, "Error", f"Request write error: {str(e)}")

    def _on_release_write(self) -> None:
        """Handle release write button click."""
        try:
            success = self._collaboration_manager.release_write()
            if success:
                self.statusBar().showMessage("Write access released.", 3000)
            else:
                QMessageBox.warning(self, "Release Write", "Failed to release write lock.")
        except Exception as e:
            logger.exception("Error releasing write")
            QMessageBox.critical(self, "Error", f"Release write error: {str(e)}")

    def _on_publish(self) -> None:
        """Handle publish button click."""
        # Check if in write mode
        if not self._collaboration_manager.is_writing():
            QMessageBox.warning(self, "Publish", "You must be in WRITE mode to publish.")
            return

        try:
            success = self._sync_service.execute_sync()
            if success:
                QMessageBox.information(self, "Publish", "Publish successful.")
            else:
                QMessageBox.warning(self, "Publish", "Publish failed. Check logs.")
        except Exception as e:
            if "conflict" in str(e).lower():
                QMessageBox.warning(self, "Publish Conflict", 
                    "Cannot publish due to repository conflict.\n"
                    "Please resolve manually or use local mode.")
            else:
                QMessageBox.critical(self, "Error", f"Publish error: {str(e)}")

    # ===== Workspace Navigation =====

    def _on_workspace_selected(self, workspace_id: str) -> None:
        """Handle workspace selection from home."""
        permission_map = {
            "student": None,
            "teacher": "teacher.view",
            "class": "class.view",
            "finance": "finance.view",
            "admin": "user.manage",
        }

        required_perm = permission_map.get(workspace_id)
        if required_perm:
            if not self._permission_helper.has_permission(required_perm):
                self.statusBar().showMessage(
                    f"Permission denied: Insufficient access rights for {workspace_id}"
                )
                logger.warning(f"Permission denied for {workspace_id}")
                return

        if workspace_id == "student":
            self.central_stack.setCurrentWidget(self.student_workspace)
            if self.student_workspace._current_student_id is not None:
                self.student_workspace.show_student(self.student_workspace._current_student_id)
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
        elif workspace_id == "admin":
            self.central_stack.setCurrentWidget(self.admin_workspace)
            self.admin_workspace.navigate_to("users")
            self.statusBar().showMessage("Admin Workspace")
        else:
            self.statusBar().showMessage(f"Workspace {workspace_id} not available")

    def _go_home(self) -> None:
        """Navigate to home."""
        self.central_stack.setCurrentWidget(self.home_page)
        self.home_page.refresh()
        self.statusBar().showMessage("Home")

    def _on_go_to_finance(self) -> None:
        """Navigate to finance workspace."""
        self._on_workspace_selected("finance")

    def _on_navigate_to_class(self, class_id: int) -> None:
        """Navigate to class detail."""
        self._on_workspace_selected("class")
        self.class_workspace.show_class(class_id)

    # ===== Helper Methods =====

    def _refresh_student_list(self) -> None:
        """Refresh student list."""
        try:
            students = self._student_service.list_students()
            self.student_workspace.list_page._students = students
            self.student_workspace.list_page.refresh()
        except Exception as e:
            logger.exception("Failed to refresh student list")

    def _apply_menu_permissions(self) -> None:
        """Apply menu permissions."""
        self.home_page.refresh()

    def _on_attendance_updated(self) -> None:
        """Handle attendance updated signal."""
        self.student_workspace.refresh_current_student()

    def _update_write_actions(self, mode: CollaborationMode) -> None:
        """Propagate write mode to all workspaces."""
        is_write = (mode == CollaborationMode.WRITE)
        for i in range(self.central_stack.count()):
            widget = self.central_stack.widget(i)
            if hasattr(widget, 'set_write_enabled'):
                widget.set_write_enabled(is_write)

    # ===== Close Event =====

    def closeEvent(self, event) -> None:
        """Handle close event."""
        if self._collaboration_manager.is_writing():
            logger.info("Releasing write lock on application close...")
            self._collaboration_manager.release_write()

        # Dispose student workspace
        if hasattr(self, 'student_workspace'):
            self.student_workspace.stop()
            self.student_workspace.dispose()

        self._sync_service.stop()
        self._collaboration_manager.shutdown()

        event.accept()