# -*- coding: utf-8 -*-
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QStackedWidget,
    QFrame, QSizePolicy
)

from centermanager.ui.workspace_navigation import WorkspaceNavigation
from centermanager.ui.workspace_header import WorkspaceHeader
from centermanager.ui.student_workspace.student_dashboard_page import StudentDashboardPage
from centermanager.ui.student_workspace.student_list_page import StudentListPage
from centermanager.ui.student_workspace.student_detail_page import StudentDetailPage
from centermanager.ui.student_workspace.student_analytics_page import StudentAnalyticsPage


class StudentWorkspaceShell(QWidget):
    go_home = Signal()
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
        permission_service,
        outstanding_service,
        attendance_service,
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
        self._student_note_service = student_note_service
        self._document_service = document_service
        self._analytics_service = analytics_service
        self._filter_service = filter_service
        self._export_service = export_service
        self._import_service = import_service
        self._income_service = income_service
        self._class_service = class_service
        self._permission_service = permission_service
        self._outstanding_service = outstanding_service
        self._attendance_service = attendance_service

        self._current_student_id: Optional[int] = None
        self._setup_ui()
        self._connect_signals()
        self.dashboard_page.refresh()
        self.navigate_to("dashboard")

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = WorkspaceHeader("Student Workspace", "Dashboard")
        self.header.back_home_clicked.connect(self.go_home.emit)
        layout.addWidget(self.header)

        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        pages = [
            {"id": "dashboard", "icon": "📊", "label": "Dashboard"},
            {"id": "students", "icon": "👨‍🎓", "label": "Students"},
            {"id": "analytics", "icon": "📈", "label": "Analytics"},
        ]
        self.nav = WorkspaceNavigation("Student Workspace", pages)
        self.nav.page_selected.connect(self.navigate_to)
        body.addWidget(self.nav)

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
            permission_service=self._permission_service,
            outstanding_service=self._outstanding_service,
            attendance_service=self._attendance_service,
        )
        self.detail_page.back_clicked.connect(self._on_back_from_detail)
        self.detail_page.student_updated.connect(self._on_student_updated)
        self.content_stack.addWidget(self.detail_page)

        # Analytics
        self.analytics_page = StudentAnalyticsPage(self._analytics_service)
        self.content_stack.addWidget(self.analytics_page)

        body.addWidget(self.content_stack, 1)
        layout.addLayout(body)

    def _connect_signals(self) -> None:
        self.nav.page_selected.connect(self.navigate_to)
        self.header.back_home_clicked.connect(self.go_home.emit)

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
        else:
            self.content_stack.setCurrentWidget(self.dashboard_page)

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

    def _on_add_action(self) -> None:
        self.list_page.show_add_dialog()

    def _on_import_action(self) -> None:
        self.list_page.show_import_dialog()

    def _on_export_action(self) -> None:
        self.list_page.export_students()

    def _on_filter_clicked(self) -> None:
        self.list_page.show_filter_dialog()

    # ====== PHƯƠNG THỨC MỚI ======
    def refresh_current_student(self) -> None:
        """Refresh the currently displayed student detail."""
        if self._current_student_id is not None:
            self.detail_page.load_student(self._current_student_id)
            # Ghi log nếu cần
            import logging
            logging.getLogger(__name__).info(f"Refreshed student detail for student {self._current_student_id}")

    @property
    def current_student_id(self) -> Optional[int]:
        """Return the ID of the student currently being viewed, or None."""
        return self._current_student_id

    def show_student(self, student_id: int) -> None:
        """Navigate to Detail Page and load the specified student."""
        self._on_student_selected(student_id)