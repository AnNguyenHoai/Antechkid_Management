# -*- coding: utf-8 -*-
"""
ClassDetailPage - full class profile with teacher assignment, student enrollment, schedule, timeline.
Attendance removed - now only in Teaching Workspace.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMessageBox, QTabWidget
)

from centermanager.models.class_ import Class
from centermanager.models.teacher import Teacher
from centermanager.models.student import Student
from centermanager.services.class_service import ClassService
from centermanager.services.class_timeline_service import ClassTimelineService
from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.student_service import StudentService
from centermanager.services.attendance_service import AttendanceService
from centermanager.ui.design_system import (
    Avatar, StatusBadge, SectionHeader, PrimaryButton, SecondaryButton
)
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.class_workspace.class_form_dialog import ClassFormDialog
from centermanager.ui.class_workspace.class_assignment_dialog import ClassAssignmentDialog
from centermanager.ui.class_workspace.class_enrollment_dialog import ClassEnrollmentDialog
from centermanager.ui.class_workspace.class_schedule_widget import ClassScheduleWidget
from centermanager.ui.session.session_dialog import SessionDialog
from centermanager.ui.timeline import TimelineWidget

logger = logging.getLogger(__name__)


class ClassDetailPage(QWidget):
    back_clicked = Signal()
    class_updated = Signal()

    def __init__(
        self,
        class_service: ClassService,
        assignment_service: TeacherAssignmentService,
        timeline_service: ClassTimelineService,
        session_service: SessionService,
        note_service: SessionNoteService,
        highlight_service: StudentHighlightService,
        student_service: StudentService,
        attendance_service: AttendanceService,   # <-- thêm
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
        self._attendance_service = attendance_service  # lưu để truyền cho schedule widget
        self._current_class_id: Optional[int] = None
        self._current_class: Optional[Class] = None

        self._setup_ui()
        self._show_empty()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar
        top_bar = QWidget()
        top_bar.setStyleSheet(f"""
            background: {COLORS['surface']};
            border-bottom: 1px solid {COLORS['border_light']};
            padding: {SPACING['xs']}px {SPACING['md']}px;
        """)
        top_bar_layout = QHBoxLayout(top_bar)
        self.back_btn = SecondaryButton("← Back")
        self.back_btn.clicked.connect(self.back_clicked.emit)
        top_bar_layout.addWidget(self.back_btn)
        top_bar_layout.addStretch()
        main_layout.addWidget(top_bar)

        # No tab widget now - chỉ có Overview
        self.overview_tab = self._create_overview_tab()
        main_layout.addWidget(self.overview_tab)

    def _create_overview_tab(self) -> QWidget:
        """Create the Overview tab content."""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(0, 0, 0, 0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        container = QWidget()
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(SPACING['md'], SPACING['lg'], SPACING['md'], SPACING['lg'])
        container_layout.setSpacing(SPACING['xl'])

        # Profile header
        self.profile_widget = QWidget()
        profile_layout = QHBoxLayout(self.profile_widget)
        profile_layout.setSpacing(SPACING['lg'])

        self.avatar = Avatar("📚", size=56)
        self.avatar.setFixedSize(56, 56)
        self.avatar.setStyleSheet("font-size: 28px; background: #e3f2fd; border-radius: 28px;")
        profile_layout.addWidget(self.avatar)

        info = QVBoxLayout()
        info.setSpacing(SPACING['xs'])
        self.name_label = QLabel()
        self.name_label.setStyleSheet(f"font-size: 22px; font-weight: 700; color: {COLORS['text_primary']};")
        info.addWidget(self.name_label)

        code_status = QHBoxLayout()
        code_status.setSpacing(SPACING['sm'])
        self.code_label = QLabel()
        self.code_label.setStyleSheet(f"font-size: 13px; color: {COLORS['text_muted']}; font-weight: 500;")
        code_status.addWidget(self.code_label)
        self.status_badge = StatusBadge("")
        code_status.addWidget(self.status_badge)
        code_status.addStretch()
        info.addLayout(code_status)

        self.course_label = QLabel()
        self.course_label.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']};")
        info.addWidget(self.course_label)

        profile_layout.addLayout(info)
        profile_layout.addStretch()

        self.edit_btn = PrimaryButton("✏️ Edit")
        self.edit_btn.setFixedHeight(34)
        self.edit_btn.clicked.connect(self._on_edit)
        profile_layout.addWidget(self.edit_btn)

        container_layout.addWidget(self.profile_widget)

        # Divider
        container_layout.addWidget(self._divider())

        # Stats
        self.stats_widget = self._create_stats()
        container_layout.addWidget(self.stats_widget)

        # Teacher Assignment
        self.teacher_section = self._create_section("👨‍🏫 Assigned Teacher")
        self.teacher_container = QWidget()
        self.teacher_layout = QVBoxLayout(self.teacher_container)
        self.teacher_layout.setSpacing(SPACING['sm'])
        self.teacher_layout.setContentsMargins(0, 0, 0, 0)
        self.teacher_section.layout().addWidget(self.teacher_container)
        container_layout.addWidget(self.teacher_section)

        # Students
        self.student_section = self._create_section("👨‍🎓 Enrolled Students")
        self.student_container = QWidget()
        self.student_layout = QVBoxLayout(self.student_container)
        self.student_layout.setSpacing(SPACING['sm'])
        self.student_layout.setContentsMargins(0, 0, 0, 0)
        self.student_section.layout().addWidget(self.student_container)
        container_layout.addWidget(self.student_section)

        # Schedule + Assessment with Add button
        schedule_section = QWidget()
        schedule_layout = QVBoxLayout(schedule_section)
        schedule_layout.setContentsMargins(0, 0, 0, 0)
        schedule_layout.setSpacing(SPACING['xs'])

        # Header with Add button
        schedule_header = QHBoxLayout()
        title_label = QLabel("📅 Weekly Schedule & Assessment")
        title_label.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {COLORS['text_primary']};")
        schedule_header.addWidget(title_label)
        schedule_header.addStretch()
        self.add_session_btn = PrimaryButton("+ Add Session")
        self.add_session_btn.setFixedHeight(30)
        self.add_session_btn.clicked.connect(self._on_add_session)
        schedule_header.addWidget(self.add_session_btn)
        schedule_layout.addLayout(schedule_header)
        schedule_layout.addWidget(self._divider())

        self.schedule_widget = ClassScheduleWidget(
            self._session_service,
            self._note_service,
            self._highlight_service,
            self._student_service,
            self._class_service,
            self._attendance_service,   # <-- truyền attendance_service
        )
        self.schedule_widget.session_updated.connect(self._on_data_changed)
        schedule_layout.addWidget(self.schedule_widget)
        container_layout.addWidget(schedule_section)

        # Timeline
        self.timeline_widget = TimelineWidget()
        timeline_section = self._create_section("📅 Timeline")
        timeline_section.layout().addWidget(self.timeline_widget)
        container_layout.addWidget(timeline_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

        return tab

    def _divider(self) -> QFrame:
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setStyleSheet(f"background-color: {COLORS['border_light']}; height: 1px;")
        return line

    def _create_section(self, title: str) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['xs'])
        title_label = QLabel(title)
        title_label.setStyleSheet(f"font-size: 16px; font-weight: 600; color: {COLORS['text_primary']};")
        layout.addWidget(title_label)
        layout.addWidget(self._divider())
        return section

    def _create_stats(self) -> QWidget:
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setSpacing(SPACING['xl'])
        self.students_label = QLabel("0 students")
        self.students_label.setStyleSheet(f"font-size: 14px; color: {COLORS['text_secondary']};")
        self.capacity_label = QLabel("Capacity: Unlimited")
        self.capacity_label.setStyleSheet(f"font-size: 14px; color: {COLORS['text_secondary']};")
        layout.addWidget(self.students_label)
        layout.addWidget(self.capacity_label)
        layout.addStretch()
        return widget

    def _show_empty(self) -> None:
        self.overview_tab.setVisible(False)

    def _show_detail(self) -> None:
        self.overview_tab.setVisible(True)

    def load_class(self, class_id: int) -> None:
        try:
            class_obj = self._class_service.get_class_with_details(class_id)
            self._current_class_id = class_obj.id
            self._current_class = class_obj
            self._populate(class_obj)
            self._show_detail()
        except Exception as e:
            logger.exception(f"Error loading class {class_id}")
            self._show_empty()

    def _populate(self, class_obj: Class) -> None:
        self.name_label.setText(class_obj.name)
        self.code_label.setText(class_obj.name)
        self.status_badge.set_status(class_obj.status or "")
        self.course_label.setText(f"Course: {class_obj.course or '-'}")
        self.students_label.setText(f"{class_obj.student_count} students")
        self.capacity_label.setText(f"Capacity: {class_obj.capacity if class_obj.capacity else 'Unlimited'}")

        # Teachers
        self._update_teachers(class_obj.teachers)

        # Students
        self._update_students()

        # Schedule
        self.schedule_widget.set_class(class_obj.id)

        # Timeline
        events = self._timeline_service.get_class_timeline(class_obj.id)
        self.timeline_widget.set_events(events)

    def _update_teachers(self, teachers: List[Teacher]) -> None:
        self._clear_layout(self.teacher_layout)

        if not teachers:
            btn = QPushButton("+ Assign Teacher")
            btn.setStyleSheet(f"color: {COLORS['primary']}; background: transparent; border: none; font-size: 14px;")
            btn.clicked.connect(self._on_assign_teacher)
            self.teacher_layout.addWidget(btn)
            return

        for teacher in teachers:
            w = QWidget()
            layout = QHBoxLayout(w)
            layout.setContentsMargins(0, 2, 0, 2)
            label = QLabel(f"{teacher.full_name} ({teacher.teacher_code})")
            label.setStyleSheet(f"font-size: 14px; color: {COLORS['text_primary']};")
            layout.addWidget(label)
            layout.addStretch()
            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet("color: #d32f2f; background: transparent; border: none;")
            remove_btn.clicked.connect(lambda checked, tid=teacher.id: self._on_remove_teacher(tid))
            layout.addWidget(remove_btn)
            self.teacher_layout.addWidget(w)

        add_btn = QPushButton("+ Assign Another Teacher")
        add_btn.setStyleSheet(f"color: {COLORS['primary']}; background: transparent; border: none; font-size: 14px;")
        add_btn.clicked.connect(self._on_assign_teacher)
        self.teacher_layout.addWidget(add_btn)

    def _update_students(self) -> None:
        self._clear_layout(self.student_layout)
        if self._current_class_id is None:
            return

        try:
            students = self._class_service.get_enrolled_students(self._current_class_id)
        except Exception as e:
            logger.exception("Error loading students")
            students = []

        if not students:
            btn = QPushButton("+ Enroll Student")
            btn.setStyleSheet(f"color: {COLORS['primary']}; background: transparent; border: none; font-size: 14px;")
            btn.clicked.connect(self._on_enroll_student)
            self.student_layout.addWidget(btn)
            return

        for student in students:
            w = QWidget()
            layout = QHBoxLayout(w)
            layout.setContentsMargins(0, 2, 0, 2)
            label = QLabel(f"{student.full_name} ({student.student_code})")
            label.setStyleSheet(f"font-size: 14px; color: {COLORS['text_primary']};")
            layout.addWidget(label)
            layout.addStretch()
            remove_btn = QPushButton("Remove")
            remove_btn.setStyleSheet("color: #d32f2f; background: transparent; border: none;")
            remove_btn.clicked.connect(lambda checked, sid=student.id: self._on_remove_student(sid))
            layout.addWidget(remove_btn)
            self.student_layout.addWidget(w)

        add_btn = QPushButton("+ Enroll Another Student")
        add_btn.setStyleSheet(f"color: {COLORS['primary']}; background: transparent; border: none; font-size: 14px;")
        add_btn.clicked.connect(self._on_enroll_student)
        self.student_layout.addWidget(add_btn)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _on_edit(self) -> None:
        if self._current_class_id is None:
            return
        dialog = ClassFormDialog(self._class_service, self._current_class_id, parent=self)
        if dialog.exec() == ClassFormDialog.DialogCode.Accepted:
            self.load_class(self._current_class_id)
            self.class_updated.emit()

    def _on_assign_teacher(self) -> None:
        if self._current_class_id is None:
            return
        dialog = ClassAssignmentDialog(
            self._class_service,
            self._current_class_id,
            parent=self
        )
        if dialog.exec() == ClassAssignmentDialog.DialogCode.Accepted:
            self.load_class(self._current_class_id)
            self.class_updated.emit()

    def _on_remove_teacher(self, teacher_id: int) -> None:
        if self._current_class_id is None:
            return
        reply = QMessageBox.question(
            self, "Confirm Remove",
            "Remove this teacher from the class?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._class_service.remove_teacher(self._current_class_id, teacher_id)
                self.load_class(self._current_class_id)
                self.class_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_enroll_student(self) -> None:
        if self._current_class_id is None:
            return
        dialog = ClassEnrollmentDialog(
            self._class_service,
            self._current_class_id,
            parent=self
        )
        if dialog.exec() == ClassEnrollmentDialog.DialogCode.Accepted:
            self.load_class(self._current_class_id)
            self.class_updated.emit()

    def _on_remove_student(self, student_id: int) -> None:
        if self._current_class_id is None:
            return
        reply = QMessageBox.question(
            self, "Confirm Remove",
            "Remove this student from the class?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._class_service.remove_student(self._current_class_id, student_id)
                self.load_class(self._current_class_id)
                self.class_updated.emit()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _on_add_session(self) -> None:
        if self._current_class_id is None:
            QMessageBox.warning(self, "Error", "No class selected.")
            return
        logger.info(f"Opening Add Session dialog for class {self._current_class_id}")
        try:
            dialog = SessionDialog(
                self._session_service,
                self._current_class_id,
                parent=self
            )
            if dialog.exec() == SessionDialog.DialogCode.Accepted:
                logger.info("Session added successfully, refreshing schedule.")
                self.schedule_widget.refresh()
                if self._current_class_id:
                    events = self._timeline_service.get_class_timeline(self._current_class_id)
                    self.timeline_widget.set_events(events)
                self.class_updated.emit()
            else:
                logger.info("Session dialog cancelled.")
        except Exception as e:
            logger.exception("Error adding session")
            QMessageBox.critical(self, "Error", f"Could not add session: {str(e)}")

    def _on_data_changed(self) -> None:
        if self._current_class_id:
            self.load_class(self._current_class_id)
            self.class_updated.emit()