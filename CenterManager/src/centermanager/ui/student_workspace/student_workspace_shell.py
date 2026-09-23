# -*- coding: utf-8 -*-
"""StudentWorkspaceShell - UI-PROD-08 Student workspace composition root."""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QThread, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QStackedWidget, QVBoxLayout, QWidget

from centermanager.events.collaboration_events import ModeChanged, WriteGranted, WriteReleased
from centermanager.events.synchronization_events import SynchronizationCompleted, VersionUpdated
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.context import PlatformContext
from centermanager.platform.sync.events import ReloadRequired
from centermanager.ui.design_system.feedback import FeedbackController
from centermanager.ui.student_workspace.student_analytics_page import StudentAnalyticsPage
from centermanager.ui.student_workspace.student_dashboard_page import StudentDashboardPage
from centermanager.ui.student_workspace.student_detail_page import StudentDetailPage
from centermanager.ui.student_workspace.student_list_page import StudentListPage
from centermanager.ui.workspace_base import WorkspaceBase
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.workspace_navigation import WorkspaceNavigation

logger = logging.getLogger(__name__)


class StudentWorkspaceShell(WorkspaceBase):
    """Production Student workspace with shared feedback and write-state projection."""

    go_home = Signal()
    go_to_finance = Signal()
    student_selected = Signal(int)

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
        student_note_service,
        document_service,
        analytics_service,
        filter_service,
        export_service,
        import_service,
        income_service,
        class_service,
        enrollment_service,
        permission_service,
        outstanding_service,
        attendance_service,
        report_service,
        platform_context: PlatformContext,
        collaboration_manager: CollaborationManager,
        notification_service,
        parent: Optional[QWidget] = None,
    ) -> None:
        self._student_service = student_service
        self._parent_service = parent_service
        self._timeline_service = timeline_service
        self._assessment_service = assessment_service
        self._summary_service = summary_service
        self._session_service = session_service
        self._note_service = note_service
        self._highlight_service = highlight_service
        self._dashboard_service = dashboard_service
        self._student_note_service = student_note_service
        self._document_service = document_service
        self._analytics_service = analytics_service
        self._filter_service = filter_service
        self._export_service = export_service
        self._import_service = import_service
        self._income_service = income_service
        self._class_service = class_service
        self._enrollment_service = enrollment_service
        self._permission_service = permission_service
        self._outstanding_service = outstanding_service
        self._attendance_service = attendance_service
        self._report_service = report_service
        self._platform_context = platform_context
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._current_student_id: Optional[int] = None
        self._event_subscriptions = []
        self._write_enabled = False
        self._feedback_host = None

        super().__init__(
            workspace_id="student",
            platform_context=platform_context,
            collaboration_manager=collaboration_manager,
            parent=parent,
        )

        # Direct construction remains possible for tests. Once attached to
        # MainWindow, this is rebound to ApplicationTopBar's shared controller.
        self._feedback_controller = FeedbackController(self)
        self._setup_ui()
        self._connect_signals()
        self.home_page = None

    @property
    def feedback_controller(self) -> FeedbackController:
        return self._feedback_controller

    def _bind_application_feedback(self) -> None:
        window = self.window()
        app_top_bar = getattr(window, "app_top_bar", None)
        controller = getattr(app_top_bar, "feedback_controller", None)
        host = getattr(app_top_bar, "feedback_host", None)

        if isinstance(controller, FeedbackController) and controller is not self._feedback_controller:
            self._feedback_controller = controller
            for page in (self.list_page, self.detail_page, self.analytics_page):
                if hasattr(page, "set_feedback_controller"):
                    page.set_feedback_controller(controller)

        if host is self._feedback_host:
            return
        if self._feedback_host is not None:
            try:
                self._feedback_host.action_triggered.disconnect(self._on_feedback_action)
            except (RuntimeError, TypeError):
                pass
        self._feedback_host = host
        if self._feedback_host is not None and hasattr(self._feedback_host, "action_triggered"):
            self._feedback_host.action_triggered.connect(self._on_feedback_action)

    def _on_feedback_action(self, action_id: str) -> None:
        routes = {
            "student-list-refresh": self.list_page.refresh,
            "student-detail-refresh": self.detail_page.refresh_current_student,
            "student-enrollment-refresh": self.detail_page.enrollment_widget.refresh,
            "student-attendance-refresh": self.detail_page.attendance_widget.refresh,
            "student-analytics-refresh": self.analytics_page.refresh,
        }
        callback = routes.get(action_id)
        if callback is not None:
            callback()

    def set_home_page(self, home_page) -> None:
        self.home_page = home_page

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = WorkspaceHeader("Student Workspace", "Dashboard")
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        pages = [
            {"id": "dashboard", "icon": "", "label": "Dashboard"},
            {"id": "students", "icon": "", "label": "Students"},
            {"id": "analytics", "icon": "", "label": "Analytics"},
        ]
        self.nav = WorkspaceNavigation("Student Workspace", pages)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        self.dashboard_page = StudentDashboardPage(self._dashboard_service)
        self.dashboard_page.add_student_clicked.connect(self._on_add_action)
        self.dashboard_page.import_students_clicked.connect(self._on_import_action)
        self.dashboard_page.export_students_clicked.connect(self._on_export_action)
        self.dashboard_page.student_selected.connect(self._on_student_selected_from_dashboard)
        self.content_stack.addWidget(self.dashboard_page)

        self.list_page = StudentListPage(
            self._student_service,
            self._parent_service,
            self._assessment_service,
            self._filter_service,
            self._import_service,
            self._export_service,
            self._platform_context,
            self._collaboration_manager,
            self._notification_service,
            feedback_controller=self._feedback_controller,
        )
        self.list_page.student_selected.connect(self._on_student_selected)
        self.list_page.filter_clicked.connect(self._on_filter_clicked)
        self.list_page.data_updated.connect(self.dashboard_page.refresh)
        self.content_stack.addWidget(self.list_page)

        self.detail_page = StudentDetailPage(
            student_service=self._student_service,
            parent_service=self._parent_service,
            timeline_service=self._timeline_service,
            assessment_service=self._assessment_service,
            summary_service=self._summary_service,
            session_service=self._session_service,
            note_service=self._note_service,
            highlight_service=self._highlight_service,
            student_note_service=self._student_note_service,
            document_service=self._document_service,
            income_service=self._income_service,
            class_service=self._class_service,
            enrollment_service=self._enrollment_service,
            permission_service=self._permission_service,
            outstanding_service=self._outstanding_service,
            attendance_service=self._attendance_service,
            report_service=self._report_service,
            platform_context=self._platform_context,
            collaboration_manager=self._collaboration_manager,
            feedback_controller=self._feedback_controller,
        )
        self.detail_page.back_clicked.connect(self._on_back_from_detail)
        self.detail_page.student_updated.connect(self._on_student_updated)
        self.detail_page.go_to_finance.connect(self._on_go_to_finance)
        self.content_stack.addWidget(self.detail_page)

        self.analytics_page = StudentAnalyticsPage(
            self._analytics_service,
            feedback_controller=self._feedback_controller,
        )
        self.content_stack.addWidget(self.analytics_page)

        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

    def _connect_signals(self) -> None:
        self.nav.page_selected.connect(self.navigate_to)
        self.header.back_home_clicked.connect(self.go_home.emit)

    def initialize(self) -> None:
        if self._is_initialized:
            return
        logger.info("[StudentWorkspace] Initializing workspace %s", self.workspace_id)
        event_bus = self._collaboration_manager._event_bus
        if event_bus:
            self._event_subscriptions.append(event_bus.register(ModeChanged, self._on_mode_changed))
            self._event_subscriptions.append(event_bus.register(WriteGranted, self._on_write_granted))
            self._event_subscriptions.append(event_bus.register(WriteReleased, self._on_write_released))
            self._event_subscriptions.append(event_bus.register(SynchronizationCompleted, self._on_sync_completed))
            self._event_subscriptions.append(event_bus.register(VersionUpdated, self._on_version_updated))
            self._event_subscriptions.append(event_bus.register(ReloadRequired, self._on_reload_required))
        self._is_initialized = True
        logger.info("[StudentWorkspace] Initialized")

    def start(self) -> None:
        logger.info("[StudentWorkspace] Starting")
        self._bind_application_feedback()
        self.refresh()

    def stop(self) -> None:
        logger.info("[StudentWorkspace] Stopping")

    def dispose(self) -> None:
        if not self._is_initialized:
            return
        logger.info("[StudentWorkspace] Disposing")
        if self._feedback_host is not None:
            try:
                self._feedback_host.action_triggered.disconnect(self._on_feedback_action)
            except (RuntimeError, TypeError):
                pass
            self._feedback_host = None
        self._event_subscriptions.clear()
        self._write_enabled = False
        self._is_initialized = False
        logger.info("[StudentWorkspace] Disposed")

    def refresh(self) -> None:
        self._bind_application_feedback()
        self.navigate_to("students")
        self.dashboard_page.refresh()
        if self._current_student_id is not None:
            self.detail_page.load_student(self._current_student_id)

    def activate(self) -> None:
        super().activate()
        self._bind_application_feedback()
        self.refresh()

    def deactivate(self) -> None:
        super().deactivate()

    def navigate_to(self, page_id: str) -> None:
        if page_id == "dashboard":
            self.content_stack.setCurrentWidget(self.dashboard_page)
            self.nav.set_active_page("dashboard")
            self.header.set_context("Student Workspace", "Dashboard")
            self.dashboard_page.refresh()
        elif page_id == "students":
            self.content_stack.setCurrentWidget(self.list_page)
            self.nav.set_active_page("students")
            self.header.set_context("Student Workspace", "Students")
            self.list_page.refresh()
        elif page_id == "analytics":
            self.content_stack.setCurrentWidget(self.analytics_page)
            self.nav.set_active_page("analytics")
            self.header.set_context("Student Workspace", "Analytics")
            self.analytics_page.refresh()

    def _on_mode_changed(self, event: ModeChanged) -> None:
        mode = event.mode if isinstance(event.mode, str) else event.mode.value
        is_write = mode == "WRITE"
        logger.debug("[StudentWorkspace] Mode changed to %s", mode)
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, lambda: self.set_write_enabled(is_write))
        else:
            self.set_write_enabled(is_write)

    def _on_write_granted(self, event: WriteGranted) -> None:
        logger.info("[StudentWorkspace] Write granted to %s", event.username)
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, lambda: self.set_write_enabled(True))
        else:
            self.set_write_enabled(True)

    def _on_write_released(self, event: WriteReleased) -> None:
        logger.info("[StudentWorkspace] Write released by %s", event.username)
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, lambda: self.set_write_enabled(False))
        else:
            self.set_write_enabled(False)

    def _on_sync_completed(self, _event: SynchronizationCompleted) -> None:
        # Background sync remains passive per UI-PROD-07: refresh without toast.
        logger.info("[StudentWorkspace] Sync completed, refreshing data")
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, self.refresh_current_student)
        else:
            self.refresh_current_student()

    def _on_version_updated(self, event: VersionUpdated) -> None:
        logger.info("[StudentWorkspace] Version updated to %s", event.new_version)

    def _on_reload_required(self, event: ReloadRequired) -> None:
        logger.info(
            "[StudentWorkspace] Reload required: version %s, reason: %s",
            event.new_version,
            event.reason,
        )
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, self._reload_required_ui)
        else:
            self._reload_required_ui()

    def _reload_required_ui(self) -> None:
        self.refresh_current_student()
        self.dashboard_page.refresh()
        self.list_page.refresh()
        if self.home_page:
            self.home_page.refresh()
        logger.info("[StudentWorkspace] Reload completed")

    def set_write_enabled(self, enabled: bool) -> None:
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, lambda: self.set_write_enabled(enabled))
            return
        self._write_enabled = bool(enabled)
        for widget in (self.dashboard_page, self.list_page, self.detail_page):
            if hasattr(widget, "set_write_enabled"):
                widget.set_write_enabled(enabled)

    def _on_student_selected(self, student_id: int) -> None:
        self._current_student_id = student_id
        self.detail_page.load_student(student_id)
        self.content_stack.setCurrentWidget(self.detail_page)
        self.nav.set_active_page("students")
        self.header.set_context("Student Workspace", "Student Detail")
        self.student_selected.emit(student_id)

    def _on_student_selected_from_dashboard(self, student_id: int) -> None:
        self._on_student_selected(student_id)

    def _on_back_from_detail(self) -> None:
        self.navigate_to("students")
        self.list_page.refresh()

    def _on_student_updated(self) -> None:
        self.list_page.refresh()
        self.dashboard_page.refresh()
        if self.home_page:
            self.home_page.refresh()

    def _on_add_action(self) -> None:
        self.list_page.show_add_dialog()

    def _on_import_action(self) -> None:
        self.list_page.show_import_dialog()

    def _on_export_action(self) -> None:
        self.list_page.export_students()

    def _on_filter_clicked(self) -> None:
        self.list_page.show_filter_dialog()

    def _on_go_to_finance(self) -> None:
        self.go_to_finance.emit()

    def refresh_current_student(self) -> None:
        if self._current_student_id is not None:
            self.detail_page.load_student(self._current_student_id)
            logger.info("[StudentWorkspace] Refreshed student %s", self._current_student_id)

    @property
    def current_student_id(self) -> Optional[int]:
        return self._current_student_id

    def show_student(self, student_id: int) -> None:
        self._on_student_selected(student_id)
