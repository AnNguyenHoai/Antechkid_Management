# -*- coding: utf-8 -*-
"""
StudentDetailPage - displays full student profile with all sections.
This is the main detail view for a student.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSplitter
)

from centermanager.services.student_service import StudentService
from centermanager.services.parent_service import ParentService
from centermanager.services.timeline_service import TimelineService
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.student_summary_service import StudentSummaryService
from centermanager.services.session_service import SessionService
from centermanager.services.session_note_service import SessionNoteService
from centermanager.services.student_highlight_service import StudentHighlightService
from centermanager.services.exceptions import StudentNotFoundError
from centermanager.models.student import Student
from centermanager.dto import StudentSummaryDTO
from centermanager.ui.students.helpers import calculate_age, format_date_for_display
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.parents import ParentCard, ParentDialog
from centermanager.ui.assessment import AssessmentSection
from centermanager.ui.timeline import TimelineWidget
from centermanager.ui.summary import SummaryWidget
from centermanager.ui.session import SessionList
from centermanager.ui.design_system import (
    SectionHeader, InfoPanel, PrimaryButton, SecondaryButton,
    DangerButton, Breadcrumb, Avatar
)
from centermanager.ui import styles

logger = logging.getLogger(__name__)


class StudentDetailPage(QWidget):
    """Full student detail view."""
    back_clicked = Signal()
    student_updated = Signal()

    def __init__(
        self,
        student_service: StudentService,
        parent_service: ParentService,
        timeline_service: TimelineService,
        assessment_service: AssessmentService,
        summary_service: StudentSummaryService,
        session_service: SessionService,
        note_service: SessionNoteService,
        highlight_service: StudentHighlightService,
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
        self._current_student_id: Optional[int] = None
        self._current_student: Optional[Student] = None

        self._setup_ui()
        self._show_empty()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Top bar with back button
        top_bar = QWidget()
        top_bar.setStyleSheet("background: white; border-bottom: 1px solid #e8e8e8; padding: 4px 12px;")
        top_bar_layout = QHBoxLayout(top_bar)
        self.back_btn = SecondaryButton("← Back")
        self.back_btn.clicked.connect(self.back_clicked.emit)
        top_bar_layout.addWidget(self.back_btn)
        top_bar_layout.addStretch()
        main_layout.addWidget(top_bar)

        # Splitter for two-column layout
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.setChildrenCollapsible(False)

        # Left panel (profile + summary)
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(12, 12, 12, 12)
        left_layout.setSpacing(16)

        # Header with avatar and name
        self.header_widget = QWidget()
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setSpacing(12)

        self.avatar_label = Avatar("", size=48)
        header_layout.addWidget(self.avatar_label)

        name_code_layout = QVBoxLayout()
        name_code_layout.setSpacing(0)
        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-size: 20px; font-weight: bold;")
        self.code_label = QLabel()
        self.code_label.setStyleSheet("color: #666; font-size: 13px;")
        name_code_layout.addWidget(self.name_label)
        name_code_layout.addWidget(self.code_label)
        header_layout.addLayout(name_code_layout)

        header_layout.addStretch()

        self.edit_btn = PrimaryButton("Edit")
        self.edit_btn.clicked.connect(self._on_edit_clicked)
        header_layout.addWidget(self.edit_btn)

        left_layout.addWidget(self.header_widget)

        # Quick Info panel
        self.info_panel = InfoPanel([
            {"label": "Age", "value": "-"},
            {"label": "Gender", "value": "-"},
            {"label": "Status", "value": "-"},
            {"label": "Level", "value": "-"},
        ])
        left_layout.addWidget(self.info_panel)

        # Summary
        self.summary_widget = SummaryWidget()
        left_layout.addWidget(self.summary_widget)

        # Parents
        self.parents_section = self._create_vertical_section("Parents")
        self.parents_container = QWidget()
        self.parents_layout = QVBoxLayout(self.parents_container)
        self.parents_layout.setSpacing(8)
        self.parents_layout.setContentsMargins(0, 0, 0, 0)
        self.parents_section.layout().addWidget(self.parents_container)
        left_layout.addWidget(self.parents_section)

        # Notes
        self.notes_section = self._create_vertical_section("Notes")
        self.notes_text_label = QLabel()
        self.notes_text_label.setWordWrap(True)
        self.notes_text_label.setStyleSheet(styles.FIELD_VALUE)
        self.notes_section.layout().addWidget(self.notes_text_label)
        left_layout.addWidget(self.notes_section)

        left_layout.addStretch()

        # Right panel (timeline, assessments, etc.)
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(12, 12, 12, 12)
        right_layout.setSpacing(16)

        # Assessment
        self.assessment_section = AssessmentSection(self._assessment_service)
        self.assessment_section.assessment_changed.connect(self._on_data_changed)
        right_layout.addWidget(self.assessment_section)

        # Timeline
        self.timeline_section = self._create_vertical_section("Timeline")
        self.timeline_widget = TimelineWidget()
        self.timeline_section.layout().addWidget(self.timeline_widget)
        right_layout.addWidget(self.timeline_section)

        right_layout.addStretch()

        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setSizes([400, 600])

        # Scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(splitter)
        main_layout.addWidget(scroll)

    def _create_vertical_section(self, title: str) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setStyleSheet(styles.SECTION_TITLE)
        layout.addWidget(title_label)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        return section

    def _show_empty(self) -> None:
        self.header_widget.setVisible(False)
        self.info_panel.setVisible(False)
        self.summary_widget.setVisible(False)
        self.parents_section.setVisible(False)
        self.notes_section.setVisible(False)
        self.assessment_section.setVisible(False)
        self.timeline_section.setVisible(False)

    def _show_detail(self) -> None:
        self.header_widget.setVisible(True)
        self.info_panel.setVisible(True)
        self.summary_widget.setVisible(True)
        self.parents_section.setVisible(True)
        self.notes_section.setVisible(True)
        self.assessment_section.setVisible(True)
        self.timeline_section.setVisible(True)

    def load_student(self, student_id: int) -> None:
        try:
            student = self._student_service.get_student(student_id)
        except StudentNotFoundError:
            logger.warning(f"Student {student_id} not found")
            self._show_empty()
            return
        except Exception as e:
            logger.exception(f"Error loading student {student_id}")
            self._show_empty()
            return

        self._current_student_id = student.id
        self._current_student = student
        self._populate_header(student)
        self._populate_info_panel(student)
        self._load_summary()
        self._load_parents()
        self._load_notes(student)
        self._load_assessment()
        self._load_timeline()
        self._show_detail()

    def _populate_header(self, student: Student) -> None:
        self.avatar_label.set_name(student.full_name)
        self.name_label.setText(student.full_name)
        self.code_label.setText(student.student_code)

    def _populate_info_panel(self, student: Student) -> None:
        age = calculate_age(student.date_of_birth)
        self.info_panel.update_value("Age", str(age) if age is not None else "-")
        self.info_panel.update_value("Gender", student.gender or "-")
        self.info_panel.update_value("Status", student.status or "-")
        self.info_panel.update_value("Level", student.current_level or "-")

    def _load_notes(self, student: Student) -> None:
        self.notes_text_label.setText(student.notes or "No notes.")

    def _load_parents(self) -> None:
        if self._current_student_id is None:
            return
        self._clear_parents()
        try:
            parents = self._parent_service.get_parents_for_student(self._current_student_id)
        except Exception as e:
            logger.exception("Error loading parents")
            parents = []

        if not parents:
            from centermanager.ui.design_system import EmptyState
            empty = EmptyState(icon="👨‍👩‍👧", title="No parents", description="Add a guardian for this student.")
            self.parents_layout.addWidget(empty)
        else:
            for parent in parents:
                card = ParentCard(parent)
                card.edit_clicked.connect(self._on_edit_parent)
                card.delete_clicked.connect(self._on_delete_parent)
                self.parents_layout.addWidget(card)
        add_btn = SecondaryButton("+ Add Parent")
        add_btn.clicked.connect(self._on_add_parent)
        self.parents_layout.addWidget(add_btn)

    def _clear_parents(self) -> None:
        while self.parents_layout.count():
            item = self.parents_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _on_add_parent(self) -> None:
        if self._current_student_id is None:
            return
        dialog = ParentDialog(self._parent_service, self._current_student_id, parent_widget=self)
        if dialog.exec() == ParentDialog.DialogCode.Accepted:
            self._load_parents()
            self._on_data_changed()

    def _on_edit_parent(self, parent_id: int) -> None:
        if self._current_student_id is None:
            return
        dialog = ParentDialog(self._parent_service, self._current_student_id, parent_id=parent_id, parent_widget=self)
        if dialog.exec() == ParentDialog.DialogCode.Accepted:
            self._load_parents()
            self._on_data_changed()

    def _on_delete_parent(self, parent_id: int) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(self, "Confirm Delete", "Delete this parent?", QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                self._parent_service.delete_parent(parent_id)
                self._load_parents()
                self._on_data_changed()
            except Exception as e:
                QMessageBox.critical(self, "Error", str(e))

    def _load_assessment(self) -> None:
        if self._current_student_id is not None:
            self.assessment_section.set_student(self._current_student_id)

    def _load_timeline(self) -> None:
        if self._current_student_id is None:
            return
        try:
            events = self._timeline_service.get_student_timeline(self._current_student_id)
            self.timeline_widget.set_events(events)
        except Exception as e:
            logger.exception("Error loading timeline")
            self.timeline_widget.set_events([])

    def _load_summary(self) -> None:
        if self._current_student_id is None:
            return
        try:
            summary = self._summary_service.get_summary(self._current_student_id)
            self.summary_widget.set_summary(summary)
        except Exception as e:
            logger.exception("Error loading summary")
            self.summary_widget.set_summary(StudentSummaryDTO())

    def _on_data_changed(self) -> None:
        if self._current_student_id is None:
            return
        self._load_parents()
        self._load_assessment()
        self._load_timeline()
        self._load_summary()
        try:
            student = self._student_service.get_student(self._current_student_id)
            self._populate_header(student)
            self._populate_info_panel(student)
            self._load_notes(student)
        except Exception:
            pass
        self.student_updated.emit()

    def _on_edit_clicked(self) -> None:
        if self._current_student_id is None:
            return
        dialog = StudentFormDialog(self._student_service, student_id=self._current_student_id, parent=self)
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self._on_data_changed()
            self.student_updated.emit()