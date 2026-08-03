# -*- coding: utf-8 -*-
import logging
from typing import Optional, List, Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QComboBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFrame, QSizePolicy, QLineEdit
)

from centermanager.models.attendance import AttendanceStatus
from centermanager.services.attendance_service import AttendanceService
from centermanager.services.session_service import SessionService
from centermanager.services.class_service import ClassService
from centermanager.models.session import Session
from centermanager.models.student import Student

logger = logging.getLogger(__name__)


class AttendanceWidget(QWidget):
    attendance_changed = Signal()

    def __init__(
        self,
        attendance_service: AttendanceService,
        session_service: SessionService,
        class_service: ClassService,
        parent: Optional[QWidget] = None
    ):
        super().__init__(parent)
        self._attendance_service = attendance_service
        self._session_service = session_service
        self._class_service = class_service
        self._class_id: Optional[int] = None
        self._sessions: List[Session] = []
        self._current_session_id: Optional[int] = None
        self._students: List[Student] = []
        self._status_combos: Dict[int, QComboBox] = {}
        self._time_edits: Dict[int, QLineEdit] = {}
        self._note_edits: Dict[int, QLineEdit] = {}

        self._setup_ui()
        self._show_empty()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Toolbar
        toolbar = QWidget()
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(8)

        self.session_combo = QComboBox()
        self.session_combo.setMinimumWidth(200)
        self.session_combo.currentIndexChanged.connect(self._on_session_selected)
        toolbar_layout.addWidget(QLabel("Session:"))
        toolbar_layout.addWidget(self.session_combo)

        toolbar_layout.addStretch()

        self.mark_all_btn = QPushButton("Mark All Present")
        self.mark_all_btn.clicked.connect(self._mark_all_present)
        toolbar_layout.addWidget(self.mark_all_btn)

        self.save_btn = QPushButton("Save Attendance")
        self.save_btn.setStyleSheet("background: #1976d2; color: white; font-weight: bold;")
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

    def _show_empty(self):
        self.table.clearSpans()
        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem("No sessions available"))
        self.table.setSpan(0, 0, 1, 4)
        self.summary_label.setText("")
        self.session_combo.clear()

    def _show_no_students(self):
        self.table.clearSpans()
        self.table.setRowCount(1)
        self.table.setItem(0, 0, QTableWidgetItem("No students enrolled in this class"))
        self.table.setSpan(0, 0, 1, 4)
        self.summary_label.setText("")
        self._status_combos.clear()
        self._time_edits.clear()
        self._note_edits.clear()

    def set_class(self, class_id: int):
        self._class_id = class_id
        self._load_sessions()

    def _load_sessions(self):
        if self._class_id is None:
            return
        try:
            self._sessions = self._session_service.get_sessions_for_class(self._class_id)
            self.session_combo.clear()
            for sess in self._sessions:
                self.session_combo.addItem(
                    f"#{sess.session_number} - {sess.scheduled_date.strftime('%d/%m/%Y')} - {sess.title}",
                    sess.id
                )
            if self._sessions:
                self._current_session_id = self._sessions[0].id
                self._load_attendance(self._current_session_id)
            else:
                self._show_empty()
        except Exception as e:
            logger.exception("Failed to load sessions")
            self._show_empty()

    def _on_session_selected(self, index):
        if index < 0:
            return
        session_id = self.session_combo.currentData()
        if session_id:
            self._current_session_id = session_id
            self._load_attendance(session_id)

    def _load_attendance(self, session_id: int):
        try:
            class_obj = self._class_service.get_class_with_details(self._class_id)
            if not class_obj or not class_obj.enrollments:
                self._show_no_students()
                return

            self._students = [e.student for e in class_obj.enrollments if e.student]
            if not self._students:
                self._show_no_students()
                return

            attendances = self._attendance_service.get_attendance_for_session(session_id)
            att_map = {a.student_id: a for a in attendances}
            self._populate_table(att_map)
            self._update_summary(attendances)
            logger.info(f"Loaded attendance for session {session_id}: {len(attendances)} records")
        except Exception as e:
            logger.exception("Failed to load attendance")
            QMessageBox.warning(self, "Error", f"Could not load attendance data: {str(e)}")
            self._show_no_students()

    def _populate_table(self, att_map: Dict[int, any]):
        # Xóa span cũ trước khi điền dữ liệu
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

            # Status combo
            combo = QComboBox()
            combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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

            # Arrival Time - editable QLineEdit
            time_edit = QLineEdit()
            time_edit.setPlaceholderText("HH:MM")
            if att and att.arrival_time:
                time_edit.setText(str(att.arrival_time))
            self.table.setCellWidget(row, 2, time_edit)
            self._time_edits[row] = time_edit

            # Teacher Note - editable QLineEdit
            note_edit = QLineEdit()
            note_edit.setPlaceholderText("Note")
            if att and att.teacher_note:
                note_edit.setText(att.teacher_note)
            self.table.setCellWidget(row, 3, note_edit)
            self._note_edits[row] = note_edit

    def _update_summary(self, attendances):
        try:
            summary = self._attendance_service.get_summary_for_session(self._current_session_id)
        except Exception:
            summary = {"Present": 0, "Late": 0, "Absent": 0, "Excused": 0}
        total = len(self._students)
        present = summary.get("Present", 0)
        late = summary.get("Late", 0)
        absent = summary.get("Absent", 0)
        excused = summary.get("Excused", 0)
        rate = (present / total * 100) if total > 0 else 0
        self.summary_label.setText(
            f"Summary: Present {present}, Late {late}, Absent {absent}, Excused {excused} | Attendance Rate: {rate:.1f}%"
        )

    def _mark_all_present(self):
        for row, combo in self._status_combos.items():
            idx = combo.findText(AttendanceStatus.PRESENT.value)
            if idx >= 0:
                combo.setCurrentIndex(idx)

    def _save_attendance(self):
        if self._current_session_id is None:
            QMessageBox.warning(self, "Error", "No session selected.")
            return

        student_statuses = {}
        for row, combo in self._status_combos.items():
            if row < len(self._students):
                student = self._students[row]
                status = combo.currentText()
                arrival_time = self._time_edits.get(row, QLineEdit()).text().strip() or None
                teacher_note = self._note_edits.get(row, QLineEdit()).text().strip() or None
                student_statuses[student.id] = {
                    "status": status,
                    "arrival_time": arrival_time,
                    "teacher_note": teacher_note
                }

        if not student_statuses:
            QMessageBox.warning(self, "Error", "No students to save.")
            return

        try:
            # Cập nhật từng học sinh
            success_count = 0
            for student_id, data in student_statuses.items():
                try:
                    self._attendance_service.create_or_update_attendance(
                        session_id=self._current_session_id,
                        student_id=student_id,
                        status=data["status"],
                        arrival_time=data["arrival_time"],
                        teacher_note=data["teacher_note"]
                    )
                    success_count += 1
                except ValueError as e:
                    logger.warning(f"Failed to save attendance for student {student_id}: {e}")
                    # Hiển thị lỗi nhưng tiếp tục với các student khác
                    QMessageBox.warning(self, "Attendance Error", f"Student {student_id}: {str(e)}")

            if success_count > 0:
                QMessageBox.information(self, "Success", f"Saved attendance for {success_count} students.")
                self.attendance_changed.emit()
                # Reload để cập nhật summary và hiển thị mới
                self._load_attendance(self._current_session_id)
            else:
                QMessageBox.critical(self, "Error", "No attendance records were saved.")
        except Exception as e:
            logger.exception("Failed to save attendance")
            QMessageBox.critical(self, "Error", str(e))

    def refresh(self):
        if self._class_id:
            self._load_sessions()