# -*- coding: utf-8 -*-
"""MainWindow - Application main window with platform integration."""

import logging
from typing import Optional

from PySide6.QtCore import Qt, QTimer, QThread
from PySide6.QtWidgets import (
    QMainWindow,
    QStackedWidget,
    QWidget,
    QVBoxLayout,
    QLabel,
    QMessageBox,
)

from centermanager.ui.application_shell import ApplicationTopBar
from centermanager.ui.design_system.tokens import COLORS, FONT_FAMILY, SPACING, TYPOGRAPHY
from centermanager.ui.home import HomePage
from centermanager.ui.student_workspace import StudentWorkspaceShell
from centermanager.ui.teacher_workspace.teacher_workspace_shell import TeacherWorkspaceShell
from centermanager.ui.class_workspace.class_workspace_shell import ClassWorkspaceShell
from centermanager.ui.finance_workspace import FinanceWorkspaceShell
from centermanager.ui.admin_workspace import AdminWorkspaceShell
from centermanager.ui.employee_workspace import EmployeeWorkspaceShell

from centermanager.services.permission_service import PermissionService
from centermanager.core.current_user import get_current_user
from centermanager.ui.permission_helpers import UIPermissionHelper

from centermanager.platform.context import PlatformContext
from centermanager.platform.collaboration import (
    CollaborationManager,
    ModeChanged,
    WriteGranted,
    WriteReleased,
    WriteRequested,
    CollaborationPoller,
    CollaborationSnapshot,
    PollerMode,
)
from centermanager.platform.sync import RuntimeSyncService
from centermanager.platform.business import BusinessModuleRegistry
from centermanager.platform.sync.events import (
    SynchronizationCompleted,
    SynchronizationFailed,
    SyncStatusChanged,
    ReloadRequired,
)

from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.events.event_bus import EventBus
from centermanager.events.student_events import (
    StudentArchived,
    StudentActivated,
    StudentDeleted,
    StudentUpdated,
    StudentEnrollmentChanged,
    StudentAssessmentChanged,
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
        employee_service,
        employee_document_service,
        employee_schedule_service,
        employee_working_time_service,
        employee_work_registration_service,
        class_service,
        enrollment_service,
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
        sync_service: Optional[RuntimeSyncService],
        module_registry: BusinessModuleRegistry,
        transaction_manager: WriteTransactionManager,
        notification_service,
        git_config_service,
        event_bus: EventBus,
        poller: Optional[CollaborationPoller] = None,
        parent: Optional[QWidget] = None,
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
        self._enrollment_service = enrollment_service
        self._employee_service = employee_service
        self._employee_document_service = employee_document_service
        self._employee_schedule_service = employee_schedule_service
        self._employee_working_time_service = employee_working_time_service
        self._employee_work_registration_service = employee_work_registration_service
        self._class_timeline_service = class_timeline_service
        self._teacher_assignment_service_for_class = teacher_assignment_service_for_class
        self._permission_service = permission_service
        self._income_service = income_service
        self._expense_service = expense_service
        self._finance_dashboard_service = finance_dashboard_service
        self._outstanding_service = outstanding_service
        self._attendance_service = attendance_service
        self._report_service = report_service

        self._platform_context = platform_context
        self._collaboration_manager = collaboration_manager
        self._sync_service = sync_service
        self._module_registry = module_registry
        self._notification_service = notification_service
        self._git_config_service = git_config_service
        self._event_bus = event_bus
        self._poller = poller

        self._transaction = transaction_manager
        self._closing_requested = False
        self._skip_auto_request_until_next_poll = False
        self._permission_helper = UIPermissionHelper(permission_service._session_factory)

        self._current_user = get_current_user()
        self._role_name = (
            self._current_user.role.name
            if self._current_user and self._current_user.role
            else None
        )

        self.setWindowTitle("CenterManager")
        self.setMinimumSize(1000, 700)
        self._setup_application_shell()

        self._setup_home()
        self._setup_student_workspace()
        self._setup_teacher_workspace()
        self._setup_class_workspace()
        self._setup_finance_workspace()
        self._setup_employee_workspace()
        self._setup_admin_workspace()

        self._setup_collaboration_status_bar()
        self._connect_collaboration_events()
        self._connect_domain_events()
        self._connect_poller()

        self.central_stack.setCurrentWidget(self.home_page)
        self.statusBar().showMessage(
            f"Welcome, {self._current_user.full_name if self._current_user else 'User'}"
        )

        self._apply_menu_permissions()
        self._refresh_student_list()
        self._update_write_buttons()

    def _setup_application_shell(self) -> None:
        """Build the global top bar + workspace content shell."""
        runtime_version = str(self._platform_context.runtime.manifest.runtime_version)
        sync_status = "disabled"
        if self._sync_service is not None:
            sync_status = str(self._sync_service.current_state().get("status", "idle"))

        root = QWidget(self)
        root.setObjectName("ApplicationShellRoot")
        root.setStyleSheet(f"background: {COLORS['surface_app']};")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        user_name = self._current_user.full_name if self._current_user else "Unknown"
        self.app_top_bar = ApplicationTopBar(
            user_name=user_name,
            role_name=self._role_name or "User",
            runtime_version=f"v{runtime_version}",
            sync_status=sync_status,
            parent=root,
        )
        self.app_top_bar.start_edit_requested.connect(self._on_start_editing)
        self.app_top_bar.finish_edit_requested.connect(self._on_finish_editing)
        self.app_top_bar.cancel_edit_requested.connect(self._on_cancel_waiting)
        layout.addWidget(self.app_top_bar)

        # Keep the long-standing application stack construction contract while
        # letting the layout re-parent it into the Application Shell V2 root.
        self.central_stack = QStackedWidget()
        layout.addWidget(self.central_stack, 1)
        self.setCentralWidget(root)
        self._shell_root = root

    # ===== Setup Methods =====

    def _setup_home(self) -> None:
        self.home_page = HomePage(home_service=self._home_service, parent=self)
        self.home_page.workspace_selected.connect(self._on_workspace_selected)
        self.central_stack.addWidget(self.home_page)

    def _setup_student_workspace(self) -> None:
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
            enrollment_service=self._enrollment_service,
            permission_service=self._permission_service,
            outstanding_service=self._outstanding_service,
            attendance_service=self._attendance_service,
            report_service=self._report_service,
            platform_context=self._platform_context,
            collaboration_manager=self._collaboration_manager,
            notification_service=self._notification_service,
        )
        self.student_workspace.go_home.connect(self._go_home)
        self.student_workspace.go_to_finance.connect(self._on_go_to_finance)
        self.central_stack.addWidget(self.student_workspace)
        self.student_workspace.initialize()
        self.student_workspace.start()

    def _setup_teacher_workspace(self) -> None:
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
            notification_service=self._notification_service,
            event_bus=self._event_bus,
        )
        self.class_workspace.go_home.connect(self._go_home)
        self.class_workspace.attendance_updated.connect(self._on_attendance_updated)
        self.central_stack.addWidget(self.class_workspace)

    def _setup_finance_workspace(self) -> None:
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
        self.finance_workspace.student_selected.connect(self._show_student_from_finance)
        self.central_stack.addWidget(self.finance_workspace)

    def _setup_employee_workspace(self) -> None:
        self.employee_workspace = EmployeeWorkspaceShell(
            self._employee_service,
            self._employee_document_service,
            self._employee_schedule_service,
            self._employee_working_time_service,
            self._employee_work_registration_service,
            self._permission_service,
        )
        self.employee_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.employee_workspace)

    def _setup_admin_workspace(self) -> None:
        self.admin_workspace = AdminWorkspaceShell(
            permission_service=self._permission_service,
            git_config_service=self._git_config_service,
            platform_context=self._platform_context,
            collaboration_manager=self._collaboration_manager,
        )
        self.admin_workspace.go_home.connect(self._go_home)
        self.central_stack.addWidget(self.admin_workspace)

    # ===== Poller Connection =====

    def _connect_poller(self) -> None:
        if self._poller is None:
            logger.debug("Poller not available, skipping connection")
            return
        self._poller.snapshot_changed.connect(self._on_poller_snapshot_changed)
        logger.info("Connected CollaborationPoller to MainWindow")

    def _on_poller_snapshot_changed(self, snapshot: CollaborationSnapshot) -> None:
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, self._update_waiting_status)
        else:
            self._update_waiting_status()

    def _update_poller_status(self) -> None:
        if self._poller is None:
            return
        try:
            self._poller.get_status()
        except Exception:
            logger.debug("Unable to read collaboration poller status", exc_info=True)

    # ===== Application write state =====

    def _setup_collaboration_status_bar(self) -> None:
        """Bind legacy transaction attributes to ApplicationTopBar V2.

        The QStatusBar remains available only for short-lived notifications.
        """
        status_bar = self.statusBar()
        status_bar.clearMessage()
        status_bar.setSizeGripEnabled(False)
        status_bar.setStyleSheet(
            f"QStatusBar {{ background: {COLORS['surface_page']}; color: {COLORS['text_muted']}; "
            f"border-top: 1px solid {COLORS['border_subtle']}; font-family: {FONT_FAMILY}; "
            f"font-size: {TYPOGRAPHY['caption']}px; padding: 0 {SPACING['sm']}px; }}"
        )

        self.mode_label = self.app_top_bar.mode_label
        self.user_label = self.app_top_bar.user_label
        self.version_label = self.app_top_bar.version_label
        self.sync_label = self.app_top_bar.sync_label

        # Legacy tests and integrations still observe this attribute directly.
        # It is intentionally hidden; the visible writer projection lives in
        # ApplicationTopBar V2 and is updated in the same method below.
        self.waiting_indicator = QLabel("● No active editor")
        self.waiting_indicator.setVisible(False)

        self.start_edit_btn = self.app_top_bar.start_edit_btn
        self.finish_edit_btn = self.app_top_bar.finish_edit_btn
        self.cancel_btn = self.app_top_bar.cancel_btn
        self.tx_state_label = self.app_top_bar.tx_state_label
        self._collab_status_widget = self.app_top_bar
        self._update_write_buttons()

    def _update_write_buttons(self) -> None:
        state = self._transaction.state
        is_editing = self._transaction.is_editing

        if state in (
            WriteTransactionState.FINISHING,
            WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION,
            WriteTransactionState.FINISHING_STALE,
        ):
            self.start_edit_btn.setVisible(False)
            self.finish_edit_btn.setVisible(False)
            self.cancel_btn.setVisible(False)
            if state == WriteTransactionState.FINISHING:
                self.app_top_bar.set_transaction_text("Finishing...")
            elif state == WriteTransactionState.FINISHING_WAITING_FOR_COLLABORATION:
                self.app_top_bar.set_transaction_text("Waiting for collaboration...")
            else:
                self.app_top_bar.set_transaction_text("Stale session - renew editing")
                self.start_edit_btn.setVisible(True)
                self.start_edit_btn.setEnabled(True)
                self.start_edit_btn.setText("Renew editing")
            self.app_top_bar.set_mode("FINISHING", "warning")
            return

        if state == WriteTransactionState.IDLE:
            self.start_edit_btn.setText("Start editing")
            self.start_edit_btn.setEnabled(True)
            self.start_edit_btn.setVisible(True)
            self.finish_edit_btn.setVisible(False)
            self.cancel_btn.setVisible(False)
            self.app_top_bar.set_transaction_text("Ready")
        elif state == WriteTransactionState.WAITING:
            self.start_edit_btn.setText("Waiting...")
            self.start_edit_btn.setEnabled(False)
            self.start_edit_btn.setVisible(True)
            self.finish_edit_btn.setVisible(False)
            self.cancel_btn.setVisible(True)
            lock_status = self._collaboration_manager.get_lock_status()
            owner = lock_status.get("owner", "Unknown")
            pos = self._transaction.get_waiting_position()
            self.app_top_bar.set_transaction_text(f"Waiting (pos {pos}) - {owner}")
            self.statusBar().showMessage(f"Waiting for write lock (held by {owner})")
        elif is_editing:
            self.start_edit_btn.setVisible(False)
            self.finish_edit_btn.setVisible(True)
            self.cancel_btn.setVisible(False)
            self.app_top_bar.set_transaction_text("Editing")
            self.statusBar().showMessage("Editing mode - click Finish when done")
        elif state == WriteTransactionState.PUBLISH_CONFLICT:
            self.start_edit_btn.setVisible(False)
            self.finish_edit_btn.setVisible(False)
            self.cancel_btn.setVisible(True)
            self.app_top_bar.set_transaction_text("Data changed on another computer")
            self.app_top_bar.set_mode("CONFLICT", "danger")
            self.app_top_bar.set_editor_state("Resolve before editing", "danger")
            self.statusBar().showMessage("MAIN conflict: please refresh and try again")
            if not getattr(self, "_conflict_dialog_shown", False):
                self._conflict_dialog_shown = True
                QMessageBox.warning(
                    self,
                    "Data Changed",
                    "The data was changed on another computer.\n\n"
                    "Please refresh before finishing your changes.",
                )
            self._update_write_actions(False)
            return
        else:
            self.start_edit_btn.setVisible(False)
            self.finish_edit_btn.setVisible(False)
            self.cancel_btn.setVisible(False)
            state_display = {
                WriteTransactionState.LOCAL_SAVED: "Saved, pending publish",
                WriteTransactionState.PUBLISHING: "Publishing...",
                WriteTransactionState.PUBLISHED: "Published",
                WriteTransactionState.FAILED: "Failed",
                WriteTransactionState.OFFLINE_PENDING_PUBLISH: "Offline, pending publish",
            }.get(state, state.name)
            self.app_top_bar.set_transaction_text(state_display)

        self._update_waiting_status()
        self._update_write_actions(is_editing)
        self._update_poller_status()

    def _update_lock_owner_display(self) -> None:
        if not self._collaboration_manager.is_initialized():
            return
        lock_status = self._collaboration_manager.get_lock_status()
        is_locked = lock_status.get("locked", False)
        owner = lock_status.get("owner") or lock_status.get("username")
        session_id = lock_status.get("session_id")
        current_session = self._collaboration_manager.get_session_id()
        if is_locked and owner:
            if session_id == current_session:
                owner_display = f"You are editing as {owner}"
            else:
                owner_display = f"{owner} is editing"
        else:
            owner_display = "No active editor"
        self.statusBar().showMessage(owner_display, 5000)
        self._update_waiting_status()

    def _update_waiting_status(self) -> None:
        """Project writer ownership to both the V2 shell and legacy observer."""
        try:
            lock_status = self._collaboration_manager.get_lock_status()
        except Exception:
            logger.exception("Failed to read collaboration lock status")
            lock_status = {}

        is_locked = lock_status.get("locked", False)
        owner = lock_status.get("owner") or lock_status.get("username")
        lock_session = lock_status.get("session_id")
        current_session = self._collaboration_manager.get_session_id()

        if self._transaction.is_editing:
            self.waiting_indicator.setText("✏️ You are editing")
            self.app_top_bar.set_mode("WRITE", "success")
            self.app_top_bar.set_editor_state("You are editing", "success")
        elif is_locked:
            owner_text = owner or "Another user"
            self.waiting_indicator.setText(f"🔒 {owner_text} is editing")
            if lock_session == current_session:
                # The collaboration lock can briefly outlive the transaction
                # projection while finishing. Treat that transient state as
                # local ownership rather than another-user contention.
                self.app_top_bar.set_mode("READ", "neutral")
                self.app_top_bar.set_editor_state("Finishing your edit session", "neutral")
            else:
                self.app_top_bar.set_mode("READ", "warning")
                self.app_top_bar.set_editor_state(f"{owner_text} is editing", "warning")
                if self._transaction.state == WriteTransactionState.WAITING:
                    self.statusBar().showMessage(
                        f"Waiting for write lock (held by {owner_text})"
                    )
        else:
            self.waiting_indicator.setText("● No active editor")
            self.app_top_bar.set_mode("READ", "neutral")
            self.app_top_bar.set_editor_state("No active editor", "neutral")

    def _update_write_actions(self, enabled: bool) -> None:
        for i in range(self.central_stack.count()):
            widget = self.central_stack.widget(i)
            if hasattr(widget, "set_write_enabled"):
                widget.set_write_enabled(enabled)

    def set_write_enabled(self, enabled: bool) -> None:
        self._update_write_actions(enabled)

    # ===== Transaction Actions =====

    def _on_start_editing(self) -> None:
        if self._transaction.state == WriteTransactionState.FINISHING_STALE:
            logger.info("Renewing stale editing session")
            self._transaction._state = WriteTransactionState.IDLE
            self._transaction._finishing_deadline = None
            self._transaction._finishing_started_at = None
            self._transaction._publish_intent = False
            self._transaction._base_main_commit = None
            self._update_write_buttons()

        if not (
            self._transaction.can_edit
            or self._transaction.state == WriteTransactionState.WAITING
        ):
            return

        def save_local() -> bool:
            logger.info("Start editing - saving local data...")
            if hasattr(self.student_workspace, "dashboard_page"):
                try:
                    self.student_workspace.dashboard_page.refresh()
                    return True
                except Exception:
                    logger.exception("Save failed")
                    return False
            return True

        success = self._transaction.start_editing(save_local)
        if success:
            self._transaction._has_changes = False
            self.statusBar().showMessage(
                "Editing started. Make your changes, then click Finish Editing.",
                3000,
            )
            self._update_write_buttons()
        else:
            self.statusBar().showMessage(
                "Could not acquire write lock. Someone else is editing.",
                3000,
            )
            self._update_write_buttons()

    def _on_finish_editing(self) -> None:
        if not self._transaction.is_editing:
            return

        def save_local() -> bool:
            logger.info("Finishing editing - saving local data...")
            self._transaction.mark_dirty()
            if hasattr(self.student_workspace, "dashboard_page"):
                try:
                    self.student_workspace.dashboard_page.refresh()
                    return True
                except Exception:
                    logger.exception("Save failed")
                    return False
            return True

        def on_publish_success():
            dirty_student_ids = list(self._transaction.dirty_student_ids)
            logger.info(
                "Post-publish Student Workspace artifact generation started: %d dirty student(s)",
                len(dirty_student_ids),
            )
            for student_id in dirty_student_ids:
                try:
                    self._report_service.generate_student_report(
                        student_id,
                        report_type="latest",
                        trigger_event="student_updated",
                        generated_by="system",
                    )
                    logger.info(
                        "Latest student report generated after publish: student_id=%s",
                        student_id,
                    )
                except Exception:
                    logger.exception(
                        "Latest student report generation failed for %s",
                        student_id,
                    )
            self.statusBar().showMessage("Changes published successfully.", 3000)
            logger.info("Publish success - updating UI")
            self._update_write_buttons()
            if hasattr(self.student_workspace, "dashboard_page"):
                self.student_workspace.dashboard_page.refresh()
            if hasattr(self.student_workspace, "list_page"):
                self.student_workspace.list_page.refresh()
            if self._closing_requested:
                self._closing_requested = False
                QTimer.singleShot(500, self.close)

        def on_publish_failure(error: str):
            logger.error(f"Publish failure: {error}")
            QMessageBox.warning(
                self,
                "Publish Failed",
                f"Could not publish changes: {error}\n\n"
                "Your changes are saved locally but not shared.\n"
                "You can Retry or Continue Offline.",
            )
            self._update_write_buttons()
            if self._closing_requested:
                self._closing_requested = False

        success = self._transaction.finish_editing(
            save_callback=save_local,
            on_publish_success=on_publish_success,
            on_publish_failure=on_publish_failure,
        )

        if success and not self._transaction.is_editing:
            self._update_waiting_status()

        self._update_write_buttons()

        if not success and self._transaction.state == WriteTransactionState.FAILED:
            self._show_publish_failure_dialog()
        if (
            not success
            and self._transaction.state == WriteTransactionState.PUBLISH_CONFLICT
        ):
            self._conflict_dialog_shown = False
            return

    def _show_publish_failure_dialog(self) -> None:
        msg = QMessageBox(self)
        msg.setWindowTitle("Publish Failed")
        msg.setText("Publishing changes failed.")
        msg.setInformativeText("What would you like to do?")
        retry_btn = msg.addButton("Retry", QMessageBox.ActionRole)
        offline_btn = msg.addButton("Continue Offline", QMessageBox.ActionRole)
        msg.exec()

        clicked = msg.clickedButton()
        if clicked == retry_btn:
            if self._transaction.retry_publish():
                self.statusBar().showMessage("Publish successful.", 3000)
                self._update_write_buttons()
            else:
                self._show_publish_failure_dialog()
        elif clicked == offline_btn:
            self._transaction.continue_offline()
            self.statusBar().showMessage(
                "Working offline. Changes will be published later.",
                3000,
            )
            self._update_write_buttons()

    # ===== Domain Event Handlers =====

    def _connect_domain_events(self) -> None:
        if self._event_bus:
            self._event_bus.register(StudentArchived, self._on_student_archived_event)
            self._event_bus.register(StudentActivated, self._on_student_activated_event)
            self._event_bus.register(StudentUpdated, self._on_student_updated_event)
            self._event_bus.register(
                StudentAssessmentChanged,
                self._on_student_assessment_changed_event,
            )
            self._event_bus.register(
                StudentEnrollmentChanged,
                self._on_student_enrollment_changed_event,
            )
            self._event_bus.register(StudentDeleted, self._on_student_deleted_event)

            from centermanager.services.parent_service import (
                ParentAdded,
                ParentUpdated,
                ParentDeleted,
            )

            self._event_bus.register(ParentAdded, self._on_parent_event)
            self._event_bus.register(ParentUpdated, self._on_parent_event)
            self._event_bus.register(ParentDeleted, self._on_parent_event)
            logger.info("MainWindow registered Student and Parent events")

    def _on_parent_event(self, event) -> None:
        if self._transaction.is_editing:
            student_id = getattr(event, "student_id", None)
            if student_id is not None:
                self._transaction.mark_student_dirty(student_id)
                logger.info(
                    "Transaction marked dirty: student aggregate parent event %s (student_id=%s)",
                    event.__class__.__name__,
                    student_id,
                )
            else:
                self._transaction.mark_dirty()
                logger.warning(
                    "Parent event %s has no student_id; only transaction marked dirty",
                    event.__class__.__name__,
                )

    def _on_student_archived_event(self, event: StudentArchived) -> None:
        if self._transaction.is_editing:
            self._transaction.mark_student_dirty(event.student_id)
            logger.info(
                f"Transaction marked dirty: student archive "
                f"(id={event.student_id}, code={event.student_code})"
            )

    def _on_student_activated_event(self, event: StudentActivated) -> None:
        if self._transaction.is_editing:
            self._transaction.mark_student_dirty(event.student_id)
            logger.info(
                f"Transaction marked dirty: student activate "
                f"(id={event.student_id}, code={event.student_code})"
            )

    def _on_student_updated_event(self, event: StudentUpdated) -> None:
        if self._transaction.is_editing:
            self._transaction.mark_student_dirty(event.student_id)
            logger.info(
                "Transaction marked dirty: student update (id=%s, code=%s)",
                event.student_id,
                event.student_code,
            )

    def _on_student_assessment_changed_event(
        self,
        event: StudentAssessmentChanged,
    ) -> None:
        if self._transaction.is_editing:
            self._transaction.mark_student_dirty(event.student_id)
            logger.info(
                "Transaction marked dirty: student assessment %s "
                "(student_id=%s, assessment_id=%s)",
                event.action,
                event.student_id,
                event.assessment_id,
            )

    def _on_student_enrollment_changed_event(
        self,
        event: StudentEnrollmentChanged,
    ) -> None:
        if self._transaction.is_editing:
            self._transaction.mark_student_dirty(event.student_id)
            logger.info(
                "Transaction marked dirty: enrollment %s "
                "(student_id=%s, enrollment_id=%s, class_id=%s)",
                event.action,
                event.student_id,
                event.enrollment_id,
                event.class_id,
            )

    def _on_student_deleted_event(self, event: StudentDeleted) -> None:
        if self._transaction.is_editing:
            self._transaction.mark_dirty()
            logger.info(
                f"Transaction marked dirty: student delete "
                f"(id={event.student_id}, code={event.student_code})"
            )

    # ===== Collaboration Event Handling =====

    def _connect_collaboration_events(self) -> None:
        self._collaboration_manager._event_bus.register(
            ModeChanged,
            self._on_mode_changed,
        )
        self._collaboration_manager._event_bus.register(
            WriteGranted,
            self._on_write_granted,
        )
        self._collaboration_manager._event_bus.register(
            WriteReleased,
            self._on_write_released,
        )

        if self._sync_service is not None:
            self._sync_service._event_bus.register(
                SyncStatusChanged,
                self._on_sync_status_changed,
            )
            self._sync_service._event_bus.register(
                SynchronizationCompleted,
                self._on_sync_completed,
            )
            self._sync_service._event_bus.register(
                SynchronizationFailed,
                self._on_sync_failed,
            )
            self._sync_service._event_bus.register(
                ReloadRequired,
                self._on_reload_required,
            )

    def _on_mode_changed(self, event: ModeChanged) -> None:
        self._update_write_buttons()

    def _on_write_granted(self, event) -> None:
        if (
            event.session_id == self._collaboration_manager.get_session_id()
            and self._transaction.state
            in (WriteTransactionState.WAITING, WriteTransactionState.GRANTING)
            and getattr(self._transaction, "_waiting_request_id", "")
            == event.request_id
        ):
            self._transaction.on_write_granted()
        self.statusBar().showMessage(
            f"Write access granted to {event.username}",
            3000,
        )
        self._update_write_buttons()
        self._update_waiting_status()

    def _on_write_released(self, event) -> None:
        self.statusBar().showMessage(
            f"Write access released by {event.username}",
            3000,
        )
        self._update_write_buttons()
        if self._transaction.state == WriteTransactionState.WAITING:
            logger.info("WriteReleased while waiting, checking auto-grant")
            QTimer.singleShot(500, self._update_waiting_status)
        if self._sync_service is not None:
            logger.info("WriteReleased: triggering check_for_updates")
            QTimer.singleShot(500, self._sync_service.check_for_updates)

    def _on_cancel_waiting(self) -> None:
        if self._transaction.state == WriteTransactionState.WAITING:
            if self._transaction.cancel_editing():
                self.statusBar().showMessage("Write request cancelled.")
                self._update_write_buttons()
            else:
                self.statusBar().showMessage(
                    "Failed to cancel request.",
                    3000,
                )

    def _on_sync_status_changed(self, event: SyncStatusChanged) -> None:
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(
                0,
                lambda: self._on_sync_status_changed_ui(event),
            )
        else:
            self._on_sync_status_changed_ui(event)

    def _on_sync_status_changed_ui(self, event: SyncStatusChanged) -> None:
        if self._sync_service is not None:
            self.app_top_bar.set_sync_status(event.new_status)
            if event.new_status == "failed":
                self.statusBar().showMessage(
                    "Synchronization failed. Check logs.",
                    3000,
                )

    def _on_sync_completed(self, event: SynchronizationCompleted) -> None:
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(
                0,
                lambda: self._on_sync_completed_ui(event),
            )
        else:
            self._on_sync_completed_ui(event)

    def _on_sync_completed_ui(self, event: SynchronizationCompleted) -> None:
        if self._sync_service is not None:
            self.statusBar().showMessage(
                f"Runtime updated to v{event.new_version}",
                3000,
            )
            self.app_top_bar.set_runtime_version(str(event.new_version))
            if self.central_stack.currentWidget() == self.student_workspace:
                self.student_workspace.refresh_current_student()

    def _on_sync_failed(self, event: SynchronizationFailed) -> None:
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(
                0,
                lambda: self._on_sync_failed_ui(event),
            )
        else:
            self._on_sync_failed_ui(event)

    def _on_sync_failed_ui(self, event: SynchronizationFailed) -> None:
        if self._sync_service is not None:
            self.app_top_bar.set_sync_status("failed")
            self.statusBar().showMessage(
                f"Sync failed: {event.error}",
                3000,
            )

    def _on_reload_required(self, event: ReloadRequired) -> None:
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(
                0,
                lambda: self._on_reload_required_ui(event),
            )
        else:
            self._on_reload_required_ui(event)

    def _on_reload_required_ui(self, event: ReloadRequired) -> None:
        logger.info(
            f"[MainWindow] Reload required: version {event.new_version}, "
            f"reason: {event.reason}"
        )
        current_widget = self.central_stack.currentWidget()
        if current_widget == self.student_workspace:
            self.student_workspace.refresh()
            self.student_workspace.refresh_current_student()
            logger.info(
                "[MainWindow] Student workspace refreshed after reload required"
            )
        elif current_widget == self.home_page:
            self.home_page.refresh()
            logger.info("[MainWindow] Home page refreshed after reload required")
        self.app_top_bar.set_runtime_version(str(event.new_version))
        self.statusBar().showMessage(
            f"Runtime updated to version {event.new_version}",
            3000,
        )

    # ===== Workspace Navigation =====

    def _on_workspace_selected(self, workspace_id: str) -> None:
        permission_map = {
            "student": None,
            "teacher": "teacher.view",
            "class": "class.view",
            "finance": "finance.view",
            "employee": None,
            "admin": "user.manage",
        }

        required_perm = permission_map.get(workspace_id)
        if required_perm:
            if not self._permission_helper.has_permission(required_perm):
                self.statusBar().showMessage(
                    f"Permission denied for {workspace_id}"
                )
                return

        if workspace_id == "employee":
            user = get_current_user()
            if not self._employee_service.can_access_workspace(user):
                self.statusBar().showMessage(
                    "Permission denied for employee workspace"
                )
                return

        if workspace_id == "student":
            self.central_stack.setCurrentWidget(self.student_workspace)
            if self.student_workspace._current_student_id is not None:
                self.student_workspace.show_student(
                    self.student_workspace._current_student_id
                )
            else:
                self.student_workspace.navigate_to("dashboard")
            self.statusBar().showMessage("Student Workspace")
            self._refresh_student_list()
            self.student_workspace.dashboard_page.refresh()
            self._update_waiting_status()
        elif workspace_id == "teacher":
            self.central_stack.setCurrentWidget(self.teacher_workspace)
            self.teacher_workspace.navigate_to("dashboard")
            self.statusBar().showMessage("Teacher Workspace")
            self._update_waiting_status()
        elif workspace_id == "class":
            self.central_stack.setCurrentWidget(self.class_workspace)
            self.class_workspace.navigate_to("dashboard")
            self.statusBar().showMessage("Class Workspace")
            self._update_waiting_status()
        elif workspace_id == "finance":
            self.central_stack.setCurrentWidget(self.finance_workspace)
            self.finance_workspace.navigate_to("dashboard")
            self.statusBar().showMessage("Finance Workspace")
            self._update_waiting_status()
        elif workspace_id == "employee":
            self.central_stack.setCurrentWidget(self.employee_workspace)
            user = get_current_user()
            if self._employee_service.can_view_all(user):
                self.employee_workspace.navigate_to("employees")
            else:
                self.employee_workspace.navigate_to("profile")
            self.statusBar().showMessage("Employee Workspace")
            self._update_waiting_status()
        elif workspace_id == "admin":
            self.central_stack.setCurrentWidget(self.admin_workspace)
            self.admin_workspace.navigate_to("users")
            self.statusBar().showMessage("Admin Workspace")
            self._update_waiting_status()
        else:
            self.statusBar().showMessage(
                f"Workspace {workspace_id} not available"
            )

    def _go_home(self) -> None:
        self.central_stack.setCurrentWidget(self.home_page)
        self.home_page.refresh()
        self.statusBar().showMessage("Home")
        self._update_waiting_status()

    def _on_go_to_finance(self) -> None:
        self._on_workspace_selected("finance")

    def _show_student_from_finance(self, student_id: int) -> None:
        """Open Student Detail from Finance Outstanding workflow."""
        self.central_stack.setCurrentWidget(self.student_workspace)
        self.student_workspace.show_student(student_id)
        self.statusBar().showMessage("Student Workspace")
        self._update_waiting_status()

    def _on_navigate_to_class(self, class_id: int) -> None:
        self._on_workspace_selected("class")
        self.class_workspace.show_class(class_id)

    # ===== Helper Methods =====

    def _refresh_student_list(self) -> None:
        try:
            students = self._student_service.list_students()
            self.student_workspace.list_page._students = students
            self.student_workspace.list_page.refresh()
        except Exception:
            logger.exception("Failed to refresh student list")

    def _apply_menu_permissions(self) -> None:
        self.home_page.refresh()

    def _on_attendance_updated(self) -> None:
        self.student_workspace.refresh_current_student()

    # ===== Close Event =====

    def closeEvent(self, event) -> None:
        if self._transaction.is_editing:
            msg = QMessageBox(self)
            msg.setWindowTitle("Unsaved Changes")
            msg.setText(
                "You are still editing.\nPlease finish editing before closing."
            )
            msg.setInformativeText("What would you like to do?")
            finish_btn = msg.addButton(
                "Finish Editing",
                QMessageBox.ActionRole,
            )
            stay_btn = msg.addButton("Stay", QMessageBox.ActionRole)
            msg.setDefaultButton(finish_btn)
            msg.exec()

            clicked = msg.clickedButton()
            if clicked == finish_btn:
                self._closing_requested = True
                self._on_finish_editing()
                event.ignore()
                return
            if clicked == stay_btn:
                event.ignore()
                return
            event.ignore()
            return

        if hasattr(self, "student_workspace"):
            self.student_workspace.stop()
            self.student_workspace.dispose()

        if self._sync_service is not None:
            self._sync_service.stop()
        if self._poller is not None:
            self._poller.stop()

        self._collaboration_manager.shutdown()
        event.accept()
