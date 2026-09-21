# -*- coding: utf-8 -*-
"""
SessionAttendanceWidget - Attendance management for a specific session.
"""
import logging
from typing import Optional, List, Dict, Callable, Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QComboBox,
    QLineEdit, QMessageBox, QFrame, QSizePolicy
)

from centermanager.models.attendance import AttendanceStatus
from centermanager.models.student import Student
from centermanager.services.attendance_service import AttendanceService
from centermanager.services.class_service import ClassService
from centermanager.ui.design_system.tokens import COLORS, SPACING

logger = logging.getLogger(__name__)


class SessionAttendanceWidget(QWidget):
    attendance_changed = Signal()
    UNMARKED_STATUS = "Not Marked"

    def __init__(
        self,
        attendance_service: AttendanceService,
        class_service: ClassService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._attendance_service = attendance_service
        # Kept for constructor compatibility with the existing Session composition.
        self._class_service = class_service
        self._session_id: Optional[int] = None
        self._class_id: Optional[int] = None
        self._students: List[Student] = []
        self._status_combos: Dict[int, QComboBox] = {}
        self._time_edits: Dict[int, QLineEdit] = {}
        self._note_edits: Dict[int, QLineEdit] = {}
        self._write_guard: Optional[Callable[[], bool]] = None
        self._notification_service: Optional[Any] = None
        self._session_lifecycle_allows_write = False

        self._setup_ui()
        self._apply_write_state()
        self._show_empty()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['sm'])

        # Toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(SPACING['sm'])

        self.mark_all_btn = QPushButton("Mark All Present")
        self.mark_all_btn.setFixedHeight(32)
        self.mark_all_btn.clicked.connect(self._mark_all_present)
        toolbar_layout.addWidget(self.mark_all_btn)

        toolbar_layout.addStretch()

        self.save_btn = QPushButton("Save Attendance")
        self.save_btn.setFixedHeight(32)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background: {COLORS['primary']};
                color: white;
                border: none;
                border-radius: 4px;
                padding: 4px 16px;
                font-weight: 500;
            }}
            QPushButton:hover {{
                background: {COLORS['primary_dark']};
            }}
        """)
        self.save_btn.clicked.connect(self._save_attendance)
        toolbar_layout.addWidget(self.save_btn)

        layout.addWidget(toolbar)

        # Table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Student", "Status", "Arrival Time", "Teacher Note"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.verticalHeader().setDefaultSectionSize(40)
        layout.addWidget(self.table)

        # Summary
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("padding: 4px; background: #f5f5f5; border-radius: 4px;")
        layout.addWidget(self.summary_label)

        # Spacer
        layout.addStretch()

    def set_write_guard(
        self,
        write_guard: Callable[[], bool],
        notification_service: Optional[Any] = None,
    ) -> None:
        """Bind the live collaboration WRITE check owned by the parent workspace."""
        self._write_guard = write_guard
        self._notification_service = notification_service
        self._apply_write_state()

    def _can_write(self) -> bool:
        if not self._session_lifecycle_allows_write:
            return False
        if self._write_guard is None:
            return False
        try:
            return bool(self._write_guard())
        except Exception:
            logger.exception("Attendance WRITE guard failed")
            return False

    def _apply_write_state(self) -> None:
        enabled = self._can_write()
        self.mark_all_btn.setEnabled(enabled)
        self.save_btn.setEnabled(enabled)
        for combo in self._status_combos.values():
            combo.setEnabled(enabled)
        for line_edit in self._time_edits.values():
            line_edit.setEnabled(enabled)
        for line_edit in self._note_edits.values():
            line_edit.setEnabled(enabled)

    def refresh_write_state(self) -> None:
        self._apply_write_state()

    def _notify_write_required(self) -> None:
        if not self._session_lifecycle_allows_write:
            message = "Attendance is read-only for Cancelled or Postponed sessions."
            title = "Attendance Read-only"
        else:
            message = "You must be in WRITE mode to save attendance."
            title = "Read-only"
        if self._notification_service is not None:
            try:
                self._notification_service.notify(message, "warning")
                return
            except Exception:
                logger.exception("Attendance WRITE warning notification failed")
        QMessageBox.warning(self, title, message)

    def _show_empty(self) -> None:
        self.table.clearSpans()
        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem("No students or no session selected"))
        self.table.setSpan(0, 0, 1, 4)
        self.summary_label.setText("")
        self._status_combos.clear()
        self._time_edits.clear()
        self._note_edits.clear()
        self._apply_write_state()

    def set_session(self, session_id: int, class_id: int) -> None:
        """Set the session and load attendance data."""
        self._session_id = session_id
        self._class_id = class_id
        try:
            self._session_lifecycle_allows_write = (
                self._attendance_service.can_edit_session_attendance(session_id)
            )
        except Exception:
            logger.exception("Failed to resolve attendance lifecycle state")
            self._session_lifecycle_allows_write = False
        self._load_data()

    def _load_data(self) -> None:
        if self._session_id is None or self._class_id is None:
            self._show_empty()
            return

        try:
            # Session owns Attendance. Roster eligibility is resolved by the
            # Attendance service for the Session date, not by today's class roster.
            self._students = self._attendance_service.get_roster_for_session(self._session_id)
            if not self._students:
                self._show_no_students()
                return

            # Load attendance for this session
            attendances = self._attendance_service.get_attendance_for_session(self._session_id)
            att_map = {a.student_id: a for a in attendances}
            self._populate_table(att_map)
            self._update_summary(attendances)

        except Exception as e:
            logger.exception("Failed to load attendance")
            self._show_empty()
            QMessageBox.warning(self, "Error", f"Could not load attendance: {str(e)}")

    def _show_no_students(self) -> None:
        self.table.clearSpans()
        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem("No students enrolled for this session date"))
        self.table.setSpan(0, 0, 1, 4)
        self.summary_label.setText("")
        self._status_combos.clear()
        self._time_edits.clear()
        self._note_edits.clear()
        self._apply_write_state()

    def _populate_table(self, att_map: Dict[int, Any]) -> None:
        self.table.clearSpans()
        self.table.setRowCount(len(self._students))
        self._status_combos.clear()
        self._time_edits.clear()
        self._note_edits.clear()

        for row, student in enumerate(self._students):
            # Student name
            name_item = QTableWidgetItem(student.full_name)
            name_item.setFlags(name_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(row, 0, name_item)

            # Status combo. A new roster row is intentionally NOT pre-marked Present.
            combo = QComboBox()
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            combo.addItem(self.UNMARKED_STATUS)
            for status in AttendanceStatus.choices():
                combo.addItem(status)
            att = att_map.get(student.id)
            if att:
                idx = combo.findText(att.status)
                if idx >= 0:
                    combo.setCurrentIndex(idx)
            else:
                combo.setCurrentIndex(0)
            self.table.setCellWidget(row, 1, combo)
            self._status_combos[row] = combo

            # Arrival time
            time_edit = QLineEdit()
            time_edit.setPlaceholderText("HH:MM")
            if att and att.arrival_time:
                time_edit.setText(str(att.arrival_time))
            self.table.setCellWidget(row, 2, time_edit)
            self._time_edits[row] = time_edit

            # Teacher note
            note_edit = QLineEdit()
            note_edit.setPlaceholderText("Note")
            if att and att.teacher_note:
                note_edit.setText(att.teacher_note)
            self.table.setCellWidget(row, 3, note_edit)
            self._note_edits[row] = note_edit

        self._apply_write_state()

    def _update_summary(self, attendances: List) -> None:
        try:
            overview = self._attendance_service.get_session_attendance_overview(self._session_id)
        except Exception:
            overview = {
                "Present": 0,
                "Late": 0,
                "Absent": 0,
                "Excused": 0,
                "Unmarked": len(self._students),
                "AttendanceRate": 0.0,
            }

        present = overview.get("Present", 0)
        late = overview.get("Late", 0)
        absent = overview.get("Absent", 0)
        excused = overview.get("Excused", 0)
        unmarked = overview.get("Unmarked", 0)
        rate = overview.get("AttendanceRate", 0.0)

        suffix = ""
        if not self._session_lifecycle_allows_write:
            suffix = "  |  Read-only: Cancelled/Postponed session"
        self.summary_label.setText(
            f"Summary: Present {present}, Late {late}, Absent {absent}, Excused {excused}, "
            f"Unmarked {unmarked}  |  Attendance Rate: {rate:.1f}%{suffix}"
        )

    def _mark_all_present(self) -> None:
        for row, combo in self._status_combos.items():
            idx = combo.findText(AttendanceStatus.PRESENT.value)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _save_attendance(self) -> None:
        # Runtime guard and Session lifecycle are authoritative even if visual state became stale.
        if not self._can_write():
            self._apply_write_state()
            self._notify_write_required()
            return

        if self._session_id is None or not self._students:
            QMessageBox.warning(self, "Error", "No session or students to save.")
            return

        unmarked_students = [
            self._students[row].full_name
            for row, combo in self._status_combos.items()
            if row < len(self._students) and combo.currentText() == self.UNMARKED_STATUS
        ]
        if unmarked_students:
            preview = ", ".join(unmarked_students[:5])
            if len(unmarked_students) > 5:
                preview += f" and {len(unmarked_students) - 5} more"
            QMessageBox.warning(
                self,
                "Incomplete Attendance",
                "Please mark attendance for every student before saving. "
                f"Unmarked: {preview}.",
            )
            return

        attendance_rows = {}
        for row, combo in self._status_combos.items():
            if row < len(self._students):
                student = self._students[row]
                attendance_rows[student.id] = {
                    "status": combo.currentText(),
                    "arrival_time": self._time_edits.get(row, QLineEdit()).text().strip() or None,
                    "teacher_note": self._note_edits.get(row, QLineEdit()).text().strip() or None,
                }

        try:
            saved = self._attendance_service.save_session_attendance(
                session_id=self._session_id,
                attendance_rows=attendance_rows,
            )
            success_count = len(saved)
            if success_count > 0:
                QMessageBox.information(self, "Success", f"Saved attendance for {success_count} students.")
                self.attendance_changed.emit()
                # Reload to update summary
                self._load_data()
            else:
                QMessageBox.critical(self, "Error", "No attendance records were saved.")
        except Exception as e:
            logger.exception("Failed to save attendance")
            QMessageBox.critical(self, "Error", str(e))

    def refresh(self) -> None:
        if self._session_id is not None and self._class_id is not None:
            self.set_session(self._session_id, self._class_id)
        else:
            self._apply_write_state()
