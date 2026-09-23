# -*- coding: utf-8 -*-
"""Read-only Student attendance projection using Design System V2 data states."""
from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from centermanager.services.attendance_service import AttendanceService
from centermanager.ui.design_system.feedback import FeedbackController
from centermanager.ui.design_system.foundation import Card
from centermanager.ui.design_system.tokens import COLORS, FONT_WEIGHTS, SPACING, TYPOGRAPHY
from centermanager.ui.shared import DataTable, TableDensity

logger = logging.getLogger(__name__)


class StudentAttendanceWidget(QWidget):
    """Attendance history with canonical loading/empty/error table states."""

    def __init__(
        self,
        attendance_service: AttendanceService,
        parent: Optional[QWidget] = None,
        feedback_controller: Optional[FeedbackController] = None,
    ) -> None:
        super().__init__(parent)
        self._attendance_service = attendance_service
        self._feedback = feedback_controller or FeedbackController(self)
        self._student_id: Optional[int] = None
        self._setup_ui()
        self._show_empty()

    def set_feedback_controller(self, controller: FeedbackController) -> None:
        self._feedback = controller

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        summary = Card(
            "Attendance summary",
            "Attendance is read-only here and is recorded from class sessions.",
            parent=self,
        )
        self.rate_label = QLabel("Attendance rate: —", summary)
        self.rate_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: {TYPOGRAPHY['section_title']}px; "
            f"font-weight: {FONT_WEIGHTS['semibold']};"
        )
        summary.add_widget(self.rate_label)
        layout.addWidget(summary)

        self.data_table = DataTable(
            [
                {"key": "date", "label": "Date", "sortable": True},
                {"key": "class", "label": "Class", "sortable": True},
                {"key": "session", "label": "Session", "sortable": False},
                {"key": "status", "label": "Status", "sortable": True},
            ],
            page_size=20,
            density=TableDensity.COMPACT,
            empty_title="No attendance records",
            empty_message="Attendance will appear after the student has recorded class sessions.",
            parent=self,
        )
        layout.addWidget(self.data_table, 1)
        # Compatibility alias retained for callers/tests that previously inspected table.
        self.table = self.data_table.table

    def _show_empty(self) -> None:
        self.data_table.set_data([], 0)
        self.rate_label.setText("Attendance rate: —")

    def set_student(self, student_id: int) -> None:
        self._student_id = student_id
        self._load_data()

    def _load_data(self) -> None:
        if self._student_id is None:
            self._show_empty()
            return
        self.data_table.set_loading(True)
        try:
            attendances = self._attendance_service.get_attendance_for_student(self._student_id)
            rows = []
            for attendance in attendances:
                session = attendance.session
                class_name = session.class_.name if session.class_ else "—"
                rows.append(
                    {
                        "date": session.scheduled_date.strftime("%d/%m/%Y"),
                        "class": class_name,
                        "session": f"#{session.session_number} - {session.title}",
                        "status": attendance.status,
                    }
                )
            self.data_table.set_data(rows, len(rows))
            if rows:
                rate = self._attendance_service.get_attendance_rate_for_student(self._student_id)
                self.rate_label.setText(f"Attendance rate: {rate:.1f}%")
            else:
                self.rate_label.setText("Attendance rate: —")
            logger.info("Loaded %s attendance records for student %s", len(rows), self._student_id)
        except Exception as exc:
            logger.exception("Failed to load student attendance")
            self.rate_label.setText("Attendance rate: unavailable")
            self.data_table.set_error(
                "Attendance records could not be loaded.",
                title="Unable to load attendance",
                retry_callback=self._load_data,
            )
            self._feedback.system_error(
                exc,
                message="Attendance records could not be loaded.",
                retry_action_id="student-attendance-refresh",
                key="student-attendance-load",
            )

    def refresh(self) -> None:
        self._load_data()

    def set_write_enabled(self, _enabled: bool) -> None:
        """Attendance is intentionally read-only from the Student workspace."""
        return
