# -*- coding: utf-8 -*-
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QFrame, QSizePolicy
)

from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.class_workspace.class_list_page import ClassListPage
from centermanager.ui.class_workspace.class_detail_page import ClassDetailPage
from centermanager.ui.class_workspace.class_dashboard_page import ClassDashboardPage
from centermanager.events.class_events import (
    ClassCreated, ClassUpdated, ClassArchived, ClassRestored, ClassSessionChanged,
)
from centermanager.events.student_events import StudentEnrollmentChanged
from centermanager.events.teacher_events import TeacherAssignmentChanged


class ClassWorkspaceShell(QWidget):
    go_home = Signal()
    attendance_updated = Signal()
    domain_class_changed = Signal(int)

    def __init__(
        self,
        class_service,
        assignment_service,
        timeline_service,
        session_service,
        note_service,
        highlight_service,
        student_service,
        attendance_service,
        platform_context=None,
        collaboration_manager=None,
        notification_service=None,
        event_bus=None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._class_service = class_service
        self._assignment_service = assignment_service
        self._timeline_service = timeline_service
        self._session_service = session_service
        self._note_service = note_service
        self._highlight_service = highlight_service
        self._student_service = student_service
        self._attendance_service = attendance_service
        self._platform_context = platform_context
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._event_bus = event_bus

        self._current_class_id: Optional[int] = None

        self._setup_ui()
        self._connect_signals()
        self._register_domain_events()
        self.navigate_to("dashboard")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = WorkspaceHeader("Class Workspace", "Dashboard")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        pages = [
            {"id": "dashboard", "icon": "📊", "label": "Dashboard"},
            {"id": "classes", "icon": "📚", "label": "Classes"},
        ]
        self.nav = WorkspaceNavigation("Class Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

        self.content_stack = QStackedWidget()
        self.content_stack.setFrameShape(QFrame.Shape.NoFrame)

        # Dashboard
        self.dashboard_page = ClassDashboardPage(
            self._class_service,
            self._session_service,
            self._timeline_service
        )
        self.content_stack.addWidget(self.dashboard_page)

        # Class List
        self.list_page = ClassListPage(
            self._class_service,
            self._assignment_service,
            self._timeline_service,
            self._collaboration_manager,
            self._notification_service,
        )
        self.list_page.class_selected.connect(self._on_class_selected)
        self.content_stack.addWidget(self.list_page)

        # Class Detail
        self.detail_page = ClassDetailPage(
            class_service=self._class_service,
            assignment_service=self._assignment_service,
            timeline_service=self._timeline_service,
            session_service=self._session_service,
            note_service=self._note_service,
            highlight_service=self._highlight_service,
            student_service=self._student_service,
            attendance_service=self._attendance_service,
            collaboration_manager=self._collaboration_manager,
            notification_service=self._notification_service,
        )
        self.detail_page.back_clicked.connect(self._on_back_from_detail)
        self.detail_page.class_updated.connect(self._on_class_updated)
        self.content_stack.addWidget(self.detail_page)

        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

    def _connect_signals(self) -> None:
        # Navigation and header signals are connected once in _setup_ui.
        # Keep this method as the extension point for future cross-page signals.
        pass

    def _register_domain_events(self) -> None:
        if self._event_bus is None:
            return

        for event_type in (
            ClassCreated,
            ClassUpdated,
            ClassArchived,
            ClassRestored,
            ClassSessionChanged,
            StudentEnrollmentChanged,
            TeacherAssignmentChanged,
        ):
            self._event_bus.register(event_type, self._on_domain_event)

        self.domain_class_changed.connect(self._refresh_for_domain_change)

    def _on_domain_event(self, event) -> None:
        class_id = getattr(event, "class_id", None)
        if class_id is None:
            return
        # Signal delivery safely queues UI work when the publisher is outside
        # the shell's Qt thread.
        self.domain_class_changed.emit(class_id)

    def _refresh_for_domain_change(self, class_id: int) -> None:
        # The list and dashboard are aggregate projections and must be refreshed
        # for every class-affecting mutation.
        self.list_page.refresh()
        self.dashboard_page.refresh()

        # Only reload detail when it is currently showing the affected class.
        if self._current_class_id == class_id:
            self.detail_page.load_class(class_id)

        self.attendance_updated.emit()

    def navigate_to(self, page_id: str) -> None:
        if page_id == "dashboard":
            self.content_stack.setCurrentWidget(self.dashboard_page)
            self.nav.set_active_page("dashboard")
            self.header.set_context("Class Workspace", "Dashboard")
            self.dashboard_page.refresh()
        elif page_id == "classes":
            self.content_stack.setCurrentWidget(self.list_page)
            self.nav.set_active_page("classes")
            self.header.set_context("Class Workspace", "Classes")
            self.list_page.refresh()

    def _on_class_selected(self, class_id: int) -> None:
        self._current_class_id = class_id
        self.detail_page.load_class(class_id)
        self.content_stack.setCurrentWidget(self.detail_page)
        self.nav.set_active_page("classes")
        self.header.set_context("Class Workspace", "Class Detail")

    def _on_back_from_detail(self) -> None:
        self.navigate_to("classes")
        self.list_page.refresh()

    def _on_class_updated(self) -> None:
        self.list_page.refresh()
        self.attendance_updated.emit()

    def show_class(self, class_id: int) -> None:
        self._current_class_id = class_id
        self.detail_page.load_class(class_id)
        self.content_stack.setCurrentWidget(self.detail_page)
        self.nav.set_active_page("classes")
        self.header.set_context("Class Workspace", "Class Detail")

    def set_write_enabled(self, enabled: bool) -> None:
        if hasattr(self.list_page, 'set_write_enabled'):
            self.list_page.set_write_enabled(enabled)
        if hasattr(self.detail_page, 'set_write_enabled'):
            self.detail_page.set_write_enabled(enabled)