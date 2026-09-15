# -*- coding: utf-8 -*-
"""StudentWorkspaceShell - Student Workspace with platform integration."""

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer, QThread
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget, QFrame

from centermanager.ui.workspace_base import WorkspaceBase
from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.student_workspace.student_dashboard_page import StudentDashboardPage
from centermanager.ui.student_workspace.student_list_page import StudentListPage
from centermanager.ui.student_workspace.student_detail_page import StudentDetailPage
from centermanager.ui.student_workspace.student_analytics_page import StudentAnalyticsPage

from centermanager.platform.context import PlatformContext
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.business import WriteGuard, PermissionGuard
from centermanager.events.collaboration_events import ModeChanged, WriteGranted, WriteReleased
from centermanager.events.synchronization_events import VersionUpdated, SynchronizationCompleted
from centermanager.platform.sync.events import ReloadRequired

logger = logging.getLogger(__name__)


class StudentWorkspaceShell(WorkspaceBase):
    """
    Student Workspace - main workspace for student management.
    Implements platform lifecycle and event integration.
    """

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
    ):
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

        # Platform
        self._platform_context = platform_context
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service

        self._current_student_id: Optional[int] = None
        self._event_subscriptions = []

        # Initialize base
        super().__init__(
            workspace_id="student",
            platform_context=platform_context,
            collaboration_manager=collaboration_manager,
            parent=parent,
        )

        self._setup_ui()
        self._connect_signals()

        # Store reference to home page (set by MainWindow)
        self.home_page = None

    def set_home_page(self, home_page):
        """Set home page reference for refresh."""
        self.home_page = home_page

    def _setup_ui(self) -> None:
        """Setup the UI components."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Header
        self.header = WorkspaceHeader("Student Workspace", "Dashboard")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        # Body
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Navigation
        pages = [
            {"id": "dashboard", "icon": "📊", "label": "Dashboard"},
            {"id": "students", "icon": "👨‍🎓", "label": "Students"},
            {"id": "analytics", "icon": "📈", "label": "Analytics"},
        ]
        self.nav = WorkspaceNavigation("Student Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        # Content stack
        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        # Dashboard
        self.dashboard_page = StudentDashboardPage(self._dashboard_service)
        self.dashboard_page.add_student_clicked.connect(self._on_add_action)
        self.dashboard_page.import_students_clicked.connect(self._on_import_action)
        self.dashboard_page.export_students_clicked.connect(self._on_export_action)
        self.dashboard_page.student_selected.connect(self._on_student_selected_from_dashboard)
        self.content_stack.addWidget(self.dashboard_page)

        # Student List
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
        )
        self.list_page.student_selected.connect(self._on_student_selected)
        self.list_page.filter_clicked.connect(self._on_filter_clicked)
        self.list_page.data_updated.connect(self.dashboard_page.refresh)
        self.content_stack.addWidget(self.list_page)

        # Student Detail
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
        )
        self.detail_page.back_clicked.connect(self._on_back_from_detail)
        self.detail_page.student_updated.connect(self._on_student_updated)
        self.detail_page.go_to_finance.connect(self._on_go_to_finance)
        self.content_stack.addWidget(self.detail_page)

        # Analytics
        self.analytics_page = StudentAnalyticsPage(self._analytics_service)
        self.content_stack.addWidget(self.analytics_page)

        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

    def _connect_signals(self) -> None:
        """Connect internal signals."""
        self.nav.page_selected.connect(self.navigate_to)
        self.header.back_home_clicked.connect(self.go_home.emit)

    # ===== Lifecycle =====

    def initialize(self) -> None:
        """Initialize workspace and subscribe to platform events."""
        if self._is_initialized:
            return
        logger.info(f"[StudentWorkspace] Initializing workspace {self.workspace_id}")

        event_bus = self._collaboration_manager._event_bus
        if event_bus:
            self._event_subscriptions.append(
                event_bus.register(ModeChanged, self._on_mode_changed)
            )
            self._event_subscriptions.append(
                event_bus.register(WriteGranted, self._on_write_granted)
            )
            self._event_subscriptions.append(
                event_bus.register(WriteReleased, self._on_write_released)
            )
            self._event_subscriptions.append(
                event_bus.register(SynchronizationCompleted, self._on_sync_completed)
            )
            self._event_subscriptions.append(
                event_bus.register(VersionUpdated, self._on_version_updated)
            )
            self._event_subscriptions.append(
                event_bus.register(ReloadRequired, self._on_reload_required)
            )

        self._is_initialized = True
        logger.info("[StudentWorkspace] Initialized")

    def start(self) -> None:
        """Start workspace operations."""
        logger.info("[StudentWorkspace] Starting")
        self.refresh()

    def stop(self) -> None:
        """Stop workspace operations."""
        logger.info("[StudentWorkspace] Stopping")

    def dispose(self) -> None:
        """Release resources and unsubscribe from events."""
        if not self._is_initialized:
            return
        logger.info("[StudentWorkspace] Disposing")
        self._event_subscriptions.clear()
        self._write_enabled = False
        self._is_initialized = False
        logger.info("[StudentWorkspace] Disposed")

    def refresh(self) -> None:
        """Refresh workspace data."""
        self.navigate_to("students")
        self.dashboard_page.refresh()
        if self._current_student_id is not None:
            self.detail_page.load_student(self._current_student_id)

    def activate(self) -> None:
        """Called when workspace becomes active."""
        super().activate()
        self.refresh()

    def deactivate(self) -> None:
        """Called when workspace becomes inactive."""
        super().deactivate()

    # ===== Navigation =====

    def navigate_to(self, page_id: str) -> None:
        """Navigate to a page within the workspace."""
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

    # ===== Event Handlers =====

    def _on_mode_changed(self, event: ModeChanged) -> None:
        """Handle mode changed event."""
        mode = event.mode if isinstance(event.mode, str) else event.mode.value
        is_write = (mode == "WRITE")
        logger.debug(f"[StudentWorkspace] Mode changed to {mode}")
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, lambda: self.set_write_enabled(is_write))
        else:
            self.set_write_enabled(is_write)

    def _on_write_granted(self, event: WriteGranted) -> None:
        """Handle write granted event."""
        logger.info(f"[StudentWorkspace] Write granted to {event.username}")
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, lambda: self.set_write_enabled(True))
        else:
            self.set_write_enabled(True)

    def _on_write_released(self, event: WriteReleased) -> None:
        """Handle write released event."""
        logger.info(f"[StudentWorkspace] Write released by {event.username}")
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, lambda: self.set_write_enabled(False))
        else:
            self.set_write_enabled(False)

    def _on_sync_completed(self, event: SynchronizationCompleted) -> None:
        """Handle sync completed event."""
        logger.info("[StudentWorkspace] Sync completed, refreshing data")
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, self.refresh_current_student)
        else:
            self.refresh_current_student()

    def _on_version_updated(self, event: VersionUpdated) -> None:
        """Handle version updated event."""
        logger.info(f"[StudentWorkspace] Version updated to {event.new_version}")

    def _on_reload_required(self, event: ReloadRequired) -> None:
        """Handle reload required event."""
        logger.info(f"[StudentWorkspace] Reload required: version {event.new_version}, reason: {event.reason}")
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, self._reload_required_ui)
        else:
            self._reload_required_ui()

    def _reload_required_ui(self) -> None:
        """UI thread version of reload required."""
        # Refresh current student data
        self.refresh_current_student()
        # Refresh dashboard and list
        self.dashboard_page.refresh()
        self.list_page.refresh()
        # Refresh home page if available
        if self.home_page:
            self.home_page.refresh()
        logger.info("[StudentWorkspace] Reload completed")

    # ===== Write state propagation =====

    def set_write_enabled(self, enabled: bool) -> None:
        """Enable/disable write actions in all child widgets."""
        if QThread.currentThread() != self.thread():
            QTimer.singleShot(0, lambda: self.set_write_enabled(enabled))
            return
        self._write_enabled = enabled
        # Central UI projection: read-only mode affects every student mutation
        # surface, while services remain protected by WriteGuard.
        for widget in [self.dashboard_page, self.list_page, self.detail_page]:
            if hasattr(widget, 'set_write_enabled'):
                widget.set_write_enabled(enabled)

    # ===== Actions =====

    def _on_student_selected(self, student_id: int) -> None:
        """Handle student selection from list."""
        self._current_student_id = student_id
        self.detail_page.load_student(student_id)
        self.content_stack.setCurrentWidget(self.detail_page)
        self.nav.set_active_page("students")
        self.header.set_context("Student Workspace", "Student Detail")
        self.student_selected.emit(student_id)

    def _on_student_selected_from_dashboard(self, student_id: int) -> None:
        """Handle student selection from dashboard."""
        self._on_student_selected(student_id)

    def _on_back_from_detail(self) -> None:
        """Navigate back from detail to list."""
        self.navigate_to("students")
        self.list_page.refresh()

    def _on_student_updated(self) -> None:
        """Refresh list and dashboard after student update."""
        self.list_page.refresh()
        self.dashboard_page.refresh()
        if self.home_page:
            self.home_page.refresh()

    def _on_add_action(self) -> None:
        """Show add student dialog."""
        self.list_page.show_add_dialog()

    def _on_import_action(self) -> None:
        """Show import student dialog."""
        self.list_page.show_import_dialog()

    def _on_export_action(self) -> None:
        """Export students."""
        self.list_page.export_students()

    def _on_filter_clicked(self) -> None:
        """Show filter dialog."""
        self.list_page.show_filter_dialog()

    def _on_go_to_finance(self) -> None:
        """Navigate to finance workspace."""
        self.go_to_finance.emit()

    def refresh_current_student(self) -> None:
        """Refresh the currently selected student."""
        if self._current_student_id is not None:
            # Đảm bảo load lại từ DB (đã được sync)
            self.detail_page.load_student(self._current_student_id)
            logger.info(f"[StudentWorkspace] Refreshed student {self._current_student_id}")

    @property
    def current_student_id(self) -> Optional[int]:
        """Get the currently selected student ID."""
        return self._current_student_id

    def show_student(self, student_id: int) -> None:
        """Show a specific student."""
        self._on_student_selected(student_id)