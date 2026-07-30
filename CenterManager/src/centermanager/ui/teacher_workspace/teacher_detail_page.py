# -*- coding: utf-8 -*-
"""
TeacherDetailPage - full teacher profile.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMessageBox
)

from centermanager.models.teacher import Teacher
from centermanager.services.teacher_service import TeacherService
from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.services.teacher_document_service import TeacherDocumentService
from centermanager.services.teacher_timeline_service import TeacherTimelineService
from centermanager.ui.design_system import (
    Avatar, StatusBadge, SectionHeader, PrimaryButton, SecondaryButton
)
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.teacher_workspace.teacher_form_dialog import TeacherFormDialog
from centermanager.ui.teacher_workspace.teacher_documents_widget import TeacherDocumentsWidget
from centermanager.ui.timeline import TimelineWidget

logger = logging.getLogger(__name__)


class TeacherDetailPage(QWidget):
    back_clicked = Signal()
    teacher_updated = Signal()

    def __init__(
        self,
        teacher_service: TeacherService,
        assignment_service: TeacherAssignmentService,
        document_service: TeacherDocumentService,
        timeline_service: TeacherTimelineService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._teacher_service = teacher_service
        self._assignment_service = assignment_service
        self._document_service = document_service
        self._timeline_service = timeline_service
        self._current_teacher_id: Optional[int] = None
        self._current_teacher: Optional[Teacher] = None

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

        self.avatar = Avatar("", size=64)
        self.avatar.setFixedSize(64, 64)
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

        self.email_phone_label = QLabel()
        self.email_phone_label.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']};")
        info.addWidget(self.email_phone_label)

        profile_layout.addLayout(info)
        profile_layout.addStretch()

        # Edit button
        self.edit_btn = PrimaryButton("✏️ Edit")
        self.edit_btn.setFixedHeight(34)
        self.edit_btn.clicked.connect(self._on_edit)
        profile_layout.addWidget(self.edit_btn)

        container_layout.addWidget(self.profile_widget)

        # Divider
        container_layout.addWidget(self._divider())

        # Professional Info
        self.professional_widget = self._create_info_panel("Professional Information", [
            ("Join Date", ""),
            ("Status", ""),
        ])
        container_layout.addWidget(self.professional_widget)

        # Assigned Classes - Read-only (loại bỏ nút "Manage Assignments")
        self.classes_widget = QWidget()
        classes_layout = QVBoxLayout(self.classes_widget)
        classes_layout.setContentsMargins(0, 0, 0, 0)
        # Chỉ hiển thị tiêu đề, không có nút hành động
        classes_header = SectionHeader("Assigned Classes")  # Không có action_text
        classes_layout.addWidget(classes_header)
        self.classes_list_label = QLabel("No classes assigned.")
        self.classes_list_label.setWordWrap(True)
        self.classes_list_label.setStyleSheet(f"font-size: 14px; color: {COLORS['text_secondary']}; padding: 8px 0;")
        classes_layout.addWidget(self.classes_list_label)
        container_layout.addWidget(self.classes_widget)

        # Documents
        self.documents_widget = TeacherDocumentsWidget(self._document_service)
        self.documents_widget.document_changed.connect(self._on_data_changed)
        container_layout.addWidget(self.documents_widget)

        # Timeline
        self.timeline_widget = TimelineWidget()
        timeline_section = self._create_section("📅 Timeline")
        timeline_section.layout().addWidget(self.timeline_widget)
        container_layout.addWidget(timeline_section)

        container_layout.addStretch()
        scroll.setWidget(container)
        main_layout.addWidget(scroll)

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

    def _create_info_panel(self, title: str, fields: list) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        header = SectionHeader(title)
        layout.addWidget(header)

        grid = QWidget()
        grid_layout = QHBoxLayout(grid)
        grid_layout.setSpacing(SPACING['xl'])

        for i, (label, value) in enumerate(fields):
            item = QWidget()
            item_layout = QVBoxLayout(item)
            item_layout.setSpacing(SPACING['xs'])
            label_w = QLabel(label)
            label_w.setStyleSheet(f"font-size: 11px; color: {COLORS['text_muted']}; font-weight: 500; letter-spacing: 0.2px;")
            value_w = QLabel(value)
            value_w.setStyleSheet(f"font-size: 14px; color: {COLORS['text_primary']}; font-weight: 500;")
            setattr(self, f"_field_{i}", value_w)
            item_layout.addWidget(label_w)
            item_layout.addWidget(value_w)
            grid_layout.addWidget(item)

        grid_layout.addStretch()
        layout.addWidget(grid)
        return widget

    def _show_empty(self) -> None:
        self.profile_widget.setVisible(False)
        self.professional_widget.setVisible(False)
        self.classes_widget.setVisible(False)
        self.documents_widget.setVisible(False)
        self.timeline_widget.setVisible(False)

    def _show_detail(self) -> None:
        self.profile_widget.setVisible(True)
        self.professional_widget.setVisible(True)
        self.classes_widget.setVisible(True)
        self.documents_widget.setVisible(True)
        self.timeline_widget.setVisible(True)

    def load_teacher(self, teacher_id: int) -> None:
        try:
            teacher = self._teacher_service.get_teacher_with_details(teacher_id)
            self._current_teacher_id = teacher.id
            self._current_teacher = teacher
            self._populate(teacher)
            self._show_detail()
        except Exception as e:
            logger.exception(f"Error loading teacher {teacher_id}")
            self._show_empty()

    def _populate(self, teacher: Teacher) -> None:
        self.avatar.set_name(teacher.full_name)
        self.name_label.setText(teacher.full_name)
        self.code_label.setText(teacher.teacher_code)
        self.status_badge.set_status(teacher.status or "")
        self.email_phone_label.setText(f"{teacher.email or '-'}  •  {teacher.phone or '-'}")

        # Professional info
        self._field_0.setText(teacher.join_date.strftime("%d/%m/%Y") if teacher.join_date else "-")
        self._field_1.setText(teacher.status or "-")

        # Assigned classes (read-only)
        if teacher.assigned_classes:
            class_names = [c.name for c in teacher.assigned_classes]
            self.classes_list_label.setText(" • " + "\n • ".join(class_names))
        else:
            self.classes_list_label.setText("No classes assigned.")

        # Documents
        self.documents_widget.set_teacher(teacher.id)

        # Timeline
        events = self._timeline_service.get_teacher_timeline(teacher.id)
        self.timeline_widget.set_events(events)

    def _on_edit(self) -> None:
        if self._current_teacher_id is None:
            return
        dialog = TeacherFormDialog(self._teacher_service, self._current_teacher_id, parent=self)
        if dialog.exec() == TeacherFormDialog.DialogCode.Accepted:
            self.load_teacher(self._current_teacher_id)
            self.teacher_updated.emit()

    def _on_data_changed(self) -> None:
        if self._current_teacher_id:
            self.load_teacher(self._current_teacher_id)
            self.teacher_updated.emit()