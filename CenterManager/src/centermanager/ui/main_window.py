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
from centermanager.platform.collaboration import CollaborationManager, CollaborationMode, ModeChanged, WriteGranted, WriteReleased
from centermanager.platform.sync import RuntimeSyncService
from centermanager.platform.business import BusinessModuleRegistry
from centermanager.platform.sync.events import (
    UpdateDetected,
    SynchronizationDeferred,
    SynchronizationStarted as SyncStarted,
    SynchronizationCompleted,
    SynchronizationFailed,
    SyncStatusChanged,
    ReloadRequired,  # <-- THÊM
)

from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState

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
        transaction_manager: WriteTransactionManager,
        notification_service: NotificationService,  # <-- THÊM
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
        self._notification_service = notification_service  # <-- LƯU

        # Write Transaction Manager
        self._transaction = transaction_manager

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

        self._update_write_buttons()

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
            notification_service=self._notification_service,  # <-- TRUYỀN
        )
        self.student_workspace.go_home.connect(self._go_home)
        self.student_workspace.go_to_finance.connect(self._on_go_to_finance)
        self.central_stack.addWidget(self.student_workspace)
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
        """Setup collaboration status bar with transaction buttons."""
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

        layout.addStretch()

        # Start Editing / Finish Editing buttons
        self.start_edit_btn = QPushButton("✏️ Start Editing")
        self.start_edit_btn.setFixedHeight(28)
        self.start_edit_btn.clicked.connect(self._on_start_editing)
        layout.addWidget(self.start_edit_btn)

        self.finish_edit_btn = QPushButton("✅ Finish Editing")
        self.finish_edit_btn.setFixedHeight(28)
        self.finish_edit_btn.setVisible(False)
        self.finish_edit_btn.clicked.connect(self._on_finish_editing)
        layout.addWidget(self.finish_edit_btn)

        self.cancel_edit_btn = QPushButton("❌ Cancel")
        self.cancel_edit_btn.setFixedHeight(28)
        self.cancel_edit_btn.setVisible(False)
        self.cancel_edit_btn.clicked.connect(self._on_cancel_editing)
        layout.addWidget(self.cancel_edit_btn)

        # Transaction state label
        self.tx_state_label = QLabel("")
        self.tx_state_label.setStyleSheet("font-size: 11px; color: #888;")
        layout.addWidget(self.tx_state_label)

        status_bar.addPermanentWidget(widget, 1)
        self._collab_status_widget = widget

        self._update_write_buttons()

    def _update_write_buttons(self) -> None:
        """Update button states based on transaction state."""
        state = self._transaction.state
        is_editing = self._transaction.is_editing
        can_edit = self._transaction.can_edit

        self.start_edit_btn.setVisible(can_edit)
        self.finish_edit_btn.setVisible(is_editing)
        self.cancel_edit_btn.setVisible(is_editing)

        mode = "WRITE" if is_editing else "READ"
        self.mode_label.setText(f"Mode: {mode}")

        state_display = {
            WriteTransactionState.IDLE: "Ready",
            WriteTransactionState.EDITING: "Editing...",
            WriteTransactionState.LOCAL_SAVED: "Saved, pending publish",
            WriteTransactionState.PUBLISHING: "Publishing...",
            WriteTransactionState.PUBLISHED: "Published",
            WriteTransactionState.COMPLETED: "Done",
            WriteTransactionState.FAILED: "Failed!",
            WriteTransactionState.OFFLINE_PENDING_PUBLISH: "Offline, pending publish",
        }.get(state, state.name)
        self.tx_state_label.setText(f"State: {state_display}")

        self.start_edit_btn.setEnabled(can_edit)
        self.finish_edit_btn.setEnabled(is_editing and state != WriteTransactionState.FAILED)
        self.cancel_edit_btn.setEnabled(is_editing)

        self._update_write_actions(is_editing)

    def _update_write_actions(self, enabled: bool) -> None:
        """Enable/disable write actions in all workspaces."""
        for i in range(self.central_stack.count()):
            widget = self.central_stack.widget(i)
            if hasattr(widget, 'set_write_enabled'):
                widget.set_write_enabled(enabled)

    # ===== Transaction Actions =====

    def _on_start_editing(self) -> None:
        """Start editing session."""
        if not self._transaction.can_edit:
            return

        def save_local() -> bool:
            logger.info("Start editing - saving local data...")
            if hasattr(self.student_workspace, 'dashboard_page'):
                try:
                    self.student_workspace.dashboard_page.refresh()
                    return True
                except Exception as e:
                    logger.exception("Save failed")
                    return False
            return True

        success = self._transaction.start_editing(save_local)
        if success:
            self._transaction._has_changes = False
            self.statusBar().showMessage("Editing started. Make your changes, then click 'Finish Editing'.", 3000)
        else:
            QMessageBox.warning(self, "Cannot Edit", "Could not acquire write lock. Another user may be editing.")
        self._update_write_buttons()

    def _on_finish_editing(self) -> None:
        if not self._transaction.is_editing:
            return

        def save_local() -> bool:
            logger.info("Finishing editing - saving local data...")
            # Mark that changes exist
            self._transaction.mark_dirty()
            if hasattr(self.student_workspace, 'dashboard_page'):
                try:
                    self.student_workspace.dashboard_page.refresh()
                    return True
                except Exception as e:
                    logger.exception("Save failed")
                    return False
            return True

        def on_publish_success():
            self.statusBar().showMessage("✅ Changes published successfully!", 3000)
            logger.info("Publish success - updating UI")
            self._update_write_buttons()
            if hasattr(self.student_workspace, 'dashboard_page'):
                self.student_workspace.dashboard_page.refresh()
            if hasattr(self.student_workspace, 'list_page'):
                self.student_workspace.list_page.refresh()

        def on_publish_failure(error: str):
            logger.error(f"Publish failure: {error}")
            QMessageBox.warning(
                self,
                "Publish Failed",
                f"Could not publish changes: {error}\n\n"
                "Your changes are saved locally but not shared.\n"
                "You can Retry, Continue Offline, or Cancel."
            )
            self._update_write_buttons()

        success = self._transaction.finish_editing(
            save_callback=save_local,
            on_publish_success=on_publish_success,
            on_publish_failure=on_publish_failure,
        )

        self._update_write_buttons()

        if not success and self._transaction.state == WriteTransactionState.FAILED:
            self._show_publish_failure_dialog()

    def _show_publish_failure_dialog(self) -> None:
        """Show dialog for publish failure options."""
        msg = QMessageBox(self)
        msg.setWindowTitle("Publish Failed")
        msg.setText("Publishing changes failed.")
        msg.setInformativeText("What would you like to do?")
        retry_btn = msg.addButton("Retry", QMessageBox.ActionRole)
        offline_btn = msg.addButton("Continue Offline", QMessageBox.ActionRole)
        cancel_btn = msg.addButton("Cancel", QMessageBox.RejectRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == retry_btn:
            if self._transaction.retry_publish():
                self.statusBar().showMessage("✅ Publish successful!", 3000)
                self._update_write_buttons()
            else:
                self._show_publish_failure_dialog()
        elif clicked == offline_btn:
            self._transaction.continue_offline()
            self.statusBar().showMessage("📡 Working offline. Changes will be published later.", 3000)
            self._update_write_buttons()
        else:
            self._transaction.cancel_editing(force=True)
            self.statusBar().showMessage("❌ Editing cancelled. Changes discarded.", 3000)
            self._update_write_buttons()

    # Trong _on_cancel_editing
    def _on_cancel_editing(self) -> None:
        """Cancel editing with confirmation if changes exist."""
        if not self._transaction.is_editing:
            return

        if self._transaction.has_changes():
            reply = QMessageBox.question(
                self,
                "Discard Changes",
                "You have unsaved changes.\n\n"
                "Cancel editing and discard all changes?",
                QMessageBox.Yes | QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
            # Discard changes with force=True to restore snapshot
            success = self._transaction.cancel_editing(force=True)
            if success:
                self.statusBar().showMessage("Editing cancelled. Changes discarded.", 2000)
            else:
                QMessageBox.critical(self, "Error", "Could not discard changes. Please try again.")
                return
        else:
            self._transaction.cancel_editing(force=False)
            self.statusBar().showMessage("Editing cancelled.", 2000)

        self._update_write_buttons()

    # ===== Collaboration Event Handling =====
    def _on_reload_required(self, event: ReloadRequired) -> None:
        """Handle reload required event."""
        logger.info(f"Reload required: version {event.new_version}, reason: {event.reason}")
        
        # Kiểm tra nếu đang ở Student Workspace
        current_widget = self.central_stack.currentWidget()
        if current_widget == self.student_workspace:
            self.student_workspace.refresh()
            logger.info("Student workspace refreshed after reload required")
        elif current_widget == self.home_page:
            self.home_page.refresh()
            logger.info("Home page refreshed after reload required")
        
        self.statusBar().showMessage(f"Runtime updated to version {event.new_version}", 3000)
    def _connect_collaboration_events(self) -> None:
        """Connect collaboration events."""
        self._collaboration_manager._event_bus.register(ModeChanged, self._on_mode_changed)
        self._collaboration_manager._event_bus.register(WriteGranted, self._on_write_granted)
        self._collaboration_manager._event_bus.register(WriteReleased, self._on_write_released)

        self._sync_service._event_bus.register(SyncStatusChanged, self._on_sync_status_changed)
        self._sync_service._event_bus.register(SynchronizationCompleted, self._on_sync_completed)
        self._sync_service._event_bus.register(SynchronizationFailed, self._on_sync_failed)
        # === THÊM: Lắng nghe ReloadRequired ===
        self._sync_service._event_bus.register(ReloadRequired, self._on_reload_required)

    def _on_mode_changed(self, event: ModeChanged) -> None:
        """Handle mode changed event."""
        self._update_write_buttons()

    def _on_write_granted(self, event) -> None:
        """Handle write granted event."""
        self.statusBar().showMessage(f"Write access granted to {event.username}", 3000)

    def _on_write_released(self, event) -> None:
        """Handle write released event."""
        self.statusBar().showMessage(f"Write access released by {event.username}", 3000)

    def _on_sync_status_changed(self, event: SyncStatusChanged) -> None:
        """Handle sync status changed event."""
        self.sync_label.setText(f"Sync: {event.new_status}")
        if event.new_status == "failed":
            self.statusBar().showMessage("Synchronization failed. Check logs.", 3000)

    def _on_sync_completed(self, event: SynchronizationCompleted) -> None:
        """Handle sync completed event."""
        self.statusBar().showMessage(f"Runtime updated to v{event.new_version}", 3000)
        self.version_label.setText(f"Runtime: v{event.new_version}")

    def _on_sync_failed(self, event: SynchronizationFailed) -> None:
        """Handle sync failed event."""
        self.statusBar().showMessage(f"Sync failed: {event.error}", 3000)

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
                self.statusBar().showMessage(f"Permission denied for {workspace_id}")
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

    # ===== Close Event =====

    def closeEvent(self, event) -> None:
        """Handle close event with transaction safety."""
        if self._transaction.is_editing:
            reply = QMessageBox.question(
                self,
                "Unsaved Changes",
                "You have unsaved changes. Do you want to finish editing before closing?",
                QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel
            )
            if reply == QMessageBox.Yes:
                self._on_finish_editing()
                if self._transaction.is_editing:
                    event.ignore()
                    return
            elif reply == QMessageBox.Cancel:
                event.ignore()
                return
            self._transaction.cancel_editing(force=True)

        if hasattr(self, 'student_workspace'):
            self.student_workspace.stop()
            self.student_workspace.dispose()

        self._sync_service.stop()
        self._collaboration_manager.shutdown()
        event.accept()