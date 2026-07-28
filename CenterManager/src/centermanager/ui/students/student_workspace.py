# -*- coding: utf-8 -*-
"""
Student Workspace – complete with Summary, Basic, Parents, Learning,
Assessment, Products, Attachments, Timeline, Notes.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QStackedWidget
)

from centermanager.services.student_service import StudentService
from centermanager.services.parent_service import ParentService
from centermanager.services.timeline_service import TimelineService
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.student_summary_service import StudentSummaryService
from centermanager.services.exceptions import StudentNotFoundError
from centermanager.models.student import Student
from centermanager.ui.students.helpers import calculate_age, format_date_for_display
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.parents.parent_card import ParentCard
from centermanager.ui.parents.parent_dialog import ParentDialog
from centermanager.ui.assessment import AssessmentSection
from centermanager.ui.timeline import TimelineWidget
from centermanager.ui.summary import SummaryWidget
from centermanager.dto.student_summary_dto import StudentSummaryDTO

logger = logging.getLogger(__name__)


class StudentWorkspace(QWidget):
    student_updated = Signal()

    def __init__(
        self,
        student_service: StudentService,
        parent_service: ParentService,
        timeline_service: TimelineService,
        assessment_service: AssessmentService,
        summary_service: StudentSummaryService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._student_service = student_service
        self._parent_service = parent_service
        self._timeline_service = timeline_service
        self._assessment_service = assessment_service
        self._summary_service = summary_service
        self._current_student_id: Optional[int] = None
        self._current_student: Optional[Student] = None

        self._setup_ui()
        self._show_empty()

    def _setup_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        self.stacked = QStackedWidget()
        main_layout.addWidget(self.stacked)

        # ----- Empty page -----
        empty_widget = QWidget()
        empty_layout = QVBoxLayout(empty_widget)
        empty_layout.setContentsMargins(0, 40, 0, 40)
        empty_layout.setSpacing(8)
        empty_layout.addStretch()
        icon_label = QLabel("👤")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_label.setStyleSheet("font-size: 40px;")
        empty_layout.addWidget(icon_label)
        empty_label = QLabel("No student selected.\nSelect a student from the list.")
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("font-size: 16px; color: #999;")
        empty_layout.addWidget(empty_label)
        empty_layout.addStretch()
        self.stacked.addWidget(empty_widget)

        # ----- Workspace page -----
        workspace_widget = QWidget()
        workspace_layout = QVBoxLayout(workspace_widget)
        workspace_layout.setContentsMargins(0, 0, 0, 0)
        workspace_layout.setSpacing(0)

        # Header
        self.header_widget = QWidget()
        self.header_widget.setStyleSheet("background-color: #f5f5f5; padding: 6px 16px;")
        self.header_widget.setFixedHeight(70)
        header_layout = QHBoxLayout(self.header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(12)

        self.avatar_label = QLabel("👤")
        self.avatar_label.setFixedSize(40, 40)
        self.avatar_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.avatar_label.setStyleSheet("font-size: 22px; background: #ddd; border-radius: 20px;")
        header_layout.addWidget(self.avatar_label)

        name_code_layout = QVBoxLayout()
        name_code_layout.setSpacing(0)
        self.name_label = QLabel()
        self.name_label.setStyleSheet("font-size: 18px; font-weight: bold;")
        self.code_label = QLabel()
        self.code_label.setStyleSheet("color: #666; font-size: 13px;")
        name_code_layout.addWidget(self.name_label)
        name_code_layout.addWidget(self.code_label)
        header_layout.addLayout(name_code_layout)

        header_layout.addStretch()

        self.edit_btn = QPushButton("Edit")
        self.edit_btn.setFixedWidth(70)
        self.export_btn = QPushButton("Export PDF")
        self.export_btn.setFixedWidth(90)
        self.export_btn.setEnabled(False)
        self.export_btn.setToolTip("Available in future version.")
        header_layout.addWidget(self.edit_btn)
        header_layout.addWidget(self.export_btn)

        workspace_layout.addWidget(self.header_widget)

        # Scroll area
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.content_widget = QWidget()
        self.content_layout = QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(24, 16, 24, 16)
        self.content_layout.setSpacing(20)
        self.scroll_area.setWidget(self.content_widget)
        workspace_layout.addWidget(self.scroll_area)

        self.stacked.addWidget(workspace_widget)

        # Build all sections
        self._build_sections()
        self.content_layout.addStretch()

        self.edit_btn.clicked.connect(self._on_edit_clicked)

    def _build_sections(self) -> None:
        # Summary (new)
        self.summary_section = self._create_section_widget("📋 Summary")
        self.summary_widget = SummaryWidget()
        self.summary_section.layout().addWidget(self.summary_widget)
        self.content_layout.addWidget(self.summary_section)

        # Basic
        self.basic_section = self._create_vertical_section("👤 Basic Information")
        self.basic_container = QWidget()
        basic_layout = QVBoxLayout(self.basic_container)
        basic_layout.setSpacing(8)
        self.pref_name_label = QLabel()
        self.dob_label = QLabel()
        self.age_label = QLabel()
        self.gender_label = QLabel()
        basic_layout.addWidget(self._create_field("Preferred Name", self.pref_name_label))
        basic_layout.addWidget(self._create_field("Date of Birth", self.dob_label))
        basic_layout.addWidget(self._create_field("Age", self.age_label))
        basic_layout.addWidget(self._create_field("Gender", self.gender_label))
        self.basic_section.layout().addWidget(self.basic_container)
        self.content_layout.addWidget(self.basic_section)

        # Parents
        self.parents_section = self._create_vertical_section("👨‍👩‍👦 Parents")
        self.parents_container = QWidget()
        self.parents_layout = QVBoxLayout(self.parents_container)
        self.parents_layout.setSpacing(8)
        self.parents_layout.setContentsMargins(0, 0, 0, 0)
        self.parents_section.layout().addWidget(self.parents_container)
        self.content_layout.addWidget(self.parents_section)

        # Learning
        self.learning_section = self._create_vertical_section("🎓 Learning")
        self.learning_container = QWidget()
        learn_layout = QVBoxLayout(self.learning_container)
        learn_layout.setSpacing(8)
        self.current_level_label = QLabel()
        self.status_label = QLabel()
        learn_layout.addWidget(self._create_field("Current Level", self.current_level_label))
        learn_layout.addWidget(self._create_field("Learning Status", self.status_label))
        self.learning_section.layout().addWidget(self.learning_container)
        self.content_layout.addWidget(self.learning_section)

        # Assessment
        self.assessment_section = AssessmentSection(self._assessment_service)
        self.assessment_section.assessment_changed.connect(self._on_data_changed)
        self.content_layout.addWidget(self.assessment_section)

        # Products (empty)
        self.products_section = self._create_empty_section("📁 Student Products", "No products.")
        self.content_layout.addWidget(self.products_section)

        # Attachments (empty)
        self.attachments_section = self._create_empty_section("📎 Attachments", "No attachments.")
        self.content_layout.addWidget(self.attachments_section)

        # Timeline
        self.timeline_section = self._create_vertical_section("📅 Timeline")
        self.timeline_widget = TimelineWidget()
        self.timeline_section.layout().addWidget(self.timeline_widget)
        self.content_layout.addWidget(self.timeline_section)

        # Notes
        self.notes_section = self._create_notes_section()
        self.content_layout.addWidget(self.notes_section)

    # ----- Helper methods -----
    def _create_section_widget(self, title: str) -> QWidget:
        section = QWidget()
        layout = QVBoxLayout(section)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        title_label = QLabel(title)
        title_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(title_label)
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        layout.addWidget(line)
        return section

    def _create_vertical_section(self, title: str) -> QWidget:
        return self._create_section_widget(title)

    def _create_empty_section(self, title: str, message: str) -> QWidget:
        section = self._create_section_widget(title)
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 8, 0, 8)
        empty_label = QLabel(message)
        empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        empty_label.setStyleSheet("color: #999; font-size: 14px; padding: 8px 0;")
        layout.addWidget(empty_label)
        section.layout().addWidget(content)
        return section

    def _create_notes_section(self) -> QWidget:
        section = self._create_section_widget("📝 Notes")
        self.notes_card = QFrame()
        self.notes_card.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.notes_card.setStyleSheet("""
            QFrame {
                border: 1px solid #ddd;
                border-radius: 4px;
                background: #fafafa;
                padding: 8px 12px;
            }
        """)
        card_layout = QVBoxLayout(self.notes_card)
        card_layout.setContentsMargins(8, 8, 8, 8)
        self.notes_text_label = QLabel()
        self.notes_text_label.setWordWrap(True)
        self.notes_text_label.setStyleSheet("font-size: 14px; color: #222;")
        card_layout.addWidget(self.notes_text_label)
        section.layout().addWidget(self.notes_card)
        return section

    def _create_field(self, label_text: str, value_widget: QLabel) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)
        label = QLabel(label_text)
        label.setStyleSheet("font-size: 13px; color: #666; font-weight: 500;")
        value_widget.setStyleSheet("font-size: 14px; color: #222;")
        layout.addWidget(label)
        layout.addWidget(value_widget)
        return w

    # ----- UI State -----
    def _show_empty(self) -> None:
        self.stacked.setCurrentIndex(0)
        self._current_student_id = None
        self._current_student = None

    def _show_workspace(self) -> None:
        self.stacked.setCurrentIndex(1)

    # ----- Load student -----
    def load_student(self, student_id: int) -> None:
        try:
            student = self._student_service.get_student(student_id)
        except StudentNotFoundError:
            logger.warning(f"Student {student_id} not found or deleted")
            self._show_empty()
            return
        except Exception as e:
            logger.exception(f"Error loading student {student_id}")
            self._show_empty()
            return

        self._current_student_id = student.id
        self._current_student = student
        self._populate_header(student)
        self._populate_basic(student)
        self._populate_learning(student)
        self._populate_notes(student)
        self._load_parents()
        self._load_assessment()
        self._load_timeline()
        self._load_summary()
        self._show_workspace()

        # Scroll to top
        self.scroll_area.verticalScrollBar().setValue(0)

    # ----- Population -----
    def _populate_header(self, student: Student) -> None:
        self.name_label.setText(student.full_name)
        self.code_label.setText(student.student_code)

    def _populate_basic(self, student: Student) -> None:
        self.pref_name_label.setText(student.preferred_name or "-")
        self.dob_label.setText(format_date_for_display(student.date_of_birth) or "-")
        age = calculate_age(student.date_of_birth)
        self.age_label.setText(str(age) if age is not None else "-")
        self.gender_label.setText(student.gender or "-")

    def _populate_learning(self, student: Student) -> None:
        self.current_level_label.setText(student.current_level or "-")
        self.status_label.setText(student.status or "-")

    def _populate_notes(self, student: Student) -> None:
        notes = student.notes
        self.notes_text_label.setText(notes if notes else "No notes.")

    # ----- Parents -----
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
            empty_widget = QWidget()
            empty_layout = QVBoxLayout(empty_widget)
            empty_layout.setContentsMargins(0, 8, 0, 8)
            empty_layout.setSpacing(4)
            icon = QLabel("👨‍👩‍👧")
            icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
            icon.setStyleSheet("font-size: 28px;")
            msg = QLabel("No parent information.\nAdd a guardian to this student.")
            msg.setAlignment(Qt.AlignmentFlag.AlignCenter)
            msg.setStyleSheet("color: #999; font-size: 14px;")
            empty_layout.addWidget(icon)
            empty_layout.addWidget(msg)
            add_btn = QPushButton("+ Add Parent")
            add_btn.setFixedWidth(120)
            add_btn.clicked.connect(self._on_add_parent)
            empty_layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignCenter)
            self.parents_layout.addWidget(empty_widget)
        else:
            for parent in parents:
                card = ParentCard(parent)
                card.edit_clicked.connect(self._on_edit_parent)
                card.delete_clicked.connect(self._on_delete_parent)
                self.parents_layout.addWidget(card)
            add_btn = QPushButton("+ Add Parent")
            add_btn.setFixedWidth(120)
            add_btn.clicked.connect(self._on_add_parent)
            self.parents_layout.addWidget(add_btn, alignment=Qt.AlignmentFlag.AlignLeft)

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
        dialog = ParentDialog(
            self._parent_service,
            self._current_student_id,
            parent_id=parent_id,
            parent_widget=self
        )
        if dialog.exec() == ParentDialog.DialogCode.Accepted:
            self._load_parents()
            self._on_data_changed()

    def _on_delete_parent(self, parent_id: int) -> None:
        from PySide6.QtWidgets import QMessageBox
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Are you sure you want to delete this parent?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._parent_service.delete_parent(parent_id)
                self._load_parents()
                self._on_data_changed()
            except Exception as e:
                logger.exception("Error deleting parent")
                QMessageBox.critical(self, "Error", "Could not delete parent.")

    # ----- Assessment -----
    def _load_assessment(self) -> None:
        if self._current_student_id is not None:
            self.assessment_section.set_student(self._current_student_id)

    # ----- Timeline -----
    def _load_timeline(self) -> None:
        if self._current_student_id is None:
            return
        try:
            events = self._timeline_service.get_student_timeline(self._current_student_id)
            self.timeline_widget.set_events(events)
        except Exception as e:
            logger.exception("Error loading timeline")
            self.timeline_widget.set_events([])

    # ----- Summary -----
    def _load_summary(self) -> None:
        if self._current_student_id is None:
            return
        try:
            summary = self._summary_service.get_summary(self._current_student_id)
            self.summary_widget.set_summary(summary)
        except Exception as e:
            logger.exception("Error loading summary")
            # Tạo DTO rỗng nếu lỗi
            self.summary_widget.set_summary(StudentSummaryDTO())

    # ----- Data Changed -----
    def _on_data_changed(self) -> None:
        """Refresh all sections after data change."""
        if self._current_student_id is None:
            return
        self._load_parents()
        self._load_assessment()
        self._load_timeline()
        self._load_summary()
        # Also refresh student basic info (if any field changed)
        try:
            student = self._student_service.get_student(self._current_student_id)
            self._populate_header(student)
            self._populate_basic(student)
            self._populate_learning(student)
            self._populate_notes(student)
        except Exception:
            pass

    # ----- Edit -----
    def _on_edit_clicked(self) -> None:
        if self._current_student_id is None:
            return
        dialog = StudentFormDialog(self._student_service, student_id=self._current_student_id, parent=self)
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self._on_data_changed()
            self.student_updated.emit()

    def refresh(self) -> None:
        if self._current_student_id is not None:
            self.load_student(self._current_student_id)
        else:
            self._show_empty()