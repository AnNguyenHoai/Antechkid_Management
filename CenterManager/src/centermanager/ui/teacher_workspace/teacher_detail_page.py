# -*- coding: utf-8 -*-
"""
TeacherDetailPage - full teacher profile.
Now with collaboration support.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QScrollArea, QFrame, QSizePolicy, QMessageBox
)

from centermanager.models.teacher import Teacher
from centermanager.core.current_user import get_current_user
from centermanager.models.role import RoleDefinitions
from centermanager.services.teacher_service import TeacherService
from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.services.teacher_document_service import TeacherDocumentService
from centermanager.services.teacher_timeline_service import TeacherTimelineService
from centermanager.ui.design_system import (
    Avatar, StatusBadge, SectionHeader, PrimaryButton, SecondaryButton
)
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.teacher_workspace.teacher_form_dialog import TeacherFormDialog
from centermanager.ui.teacher_workspace.teacher_assignment_dialog import TeacherAssignmentDialog
from centermanager.ui.teacher_workspace.teacher_documents_widget import TeacherDocumentsWidget
from centermanager.ui.timeline import TimelineWidget
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService

logger = logging.getLogger(__name__)


class TeacherDetailPage(QWidget):
    back_clicked = Signal()
    teacher_updated = Signal()
    class_clicked = Signal(int)

    def __init__(
        self,
        teacher_service: TeacherService,
        assignment_service: TeacherAssignmentService,
        document_service: TeacherDocumentService,
        timeline_service: TeacherTimelineService,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._teacher_service = teacher_service
        self._assignment_service = assignment_service
        self._document_service = document_service
        self._timeline_service = timeline_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
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

        self.restore_btn = PrimaryButton("↩ Restore")
        self.restore_btn.setFixedHeight(34)
        self.restore_btn.clicked.connect(self._on_restore)
        self.restore_btn.setVisible(False)
        profile_layout.addWidget(self.restore_btn)

        container_layout.addWidget(self.profile_widget)

        # Divider
        container_layout.addWidget(self._divider())

        # Professional Info
        self.professional_widget = self._create_info_panel("Professional Information", [
            ("Join Date", ""),
            ("Status", ""),
        ])
        container_layout.addWidget(self.professional_widget)

        # Assigned Classes
        self.classes_widget = QWidget()
        classes_layout = QVBoxLayout(self.classes_widget)
        classes_layout.setContentsMargins(0, 0, 0, 0)
        classes_header_row = QHBoxLayout()
        classes_header = SectionHeader("Assigned Classes")
        classes_header_row.addWidget(classes_header)
        classes_header_row.addStretch()
        self.manage_classes_btn = SecondaryButton("Manage Classes")
        self.manage_classes_btn.setFixedHeight(32)
        self.manage_classes_btn.clicked.connect(self._on_manage_classes)
        classes_header_row.addWidget(self.manage_classes_btn)
        classes_layout.addLayout(classes_header_row)
        self.classes_container = QWidget()
        self.classes_container_layout = QVBoxLayout(self.classes_container)
        self.classes_container_layout.setSpacing(SPACING['sm'])
        self.classes_container_layout.setContentsMargins(0, 0, 0, 0)
        classes_layout.addWidget(self.classes_container)
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
            try:
                teacher = self._teacher_service.get_teacher_with_details(teacher_id)
            except Exception:
                teacher = self._teacher_service.get_archived_teacher(teacher_id)
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
        status_text = "ARCHIVED" if teacher.deleted_at is not None else (teacher.status or "")
        self.status_badge.set_status(status_text)
        self.restore_btn.setVisible(teacher.deleted_at is not None)
        self.edit_btn.setVisible(teacher.deleted_at is None)
        self.manage_classes_btn.setEnabled(
            teacher.deleted_at is None
            and self.edit_btn.isEnabled()
            and self._can_manage_class_assignments()
        )
        self.email_phone_label.setText(f"{teacher.email or '-'}  •  {teacher.phone or '-'}")

        # Professional info
        self._field_0.setText(teacher.join_date.strftime("%d/%m/%Y") if teacher.join_date else "-")
        self._field_1.setText(teacher.status or "-")

        # Assigned classes
        self._update_classes(teacher.assigned_classes)

        # Documents
        self.documents_widget.set_teacher(teacher.id)

        # Timeline
        events = self._timeline_service.get_teacher_timeline(teacher.id)
        self.timeline_widget.set_events(events)

    def _update_classes(self, classes) -> None:
        while self.classes_container_layout.count():
            child = self.classes_container_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        if not classes:
            label = QLabel("No classes assigned.")
            label.setStyleSheet(f"font-size: 14px; color: {COLORS['text_secondary']}; padding: 8px 0;")
            self.classes_container_layout.addWidget(label)
            return

        for cls in classes:
            btn = QPushButton(f"📚 {cls.name}")
            btn.setStyleSheet(f"""
                QPushButton {{
                    text-align: left;
                    background: {COLORS['surface_hover']};
                    border: 1px solid {COLORS['border_light']};
                    border-radius: 4px;
                    padding: 8px 12px;
                    font-size: 14px;
                    color: {COLORS['primary']};
                }}
                QPushButton:hover {{
                    background: {COLORS['primary_hover']};
                    border-color: {COLORS['primary']};
                }}
            """)
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, cid=cls.id: self.class_clicked.emit(cid))
            self.classes_container_layout.addWidget(btn)

    def _can_manage_class_assignments(self) -> bool:
        """Only administrators and managers may change teacher assignments."""
        user = get_current_user()
        role_name = (
            getattr(getattr(user, "role", None), "name", None)
            if user is not None
            else None
        )
        return role_name in {
            RoleDefinitions.ADMIN,
            RoleDefinitions.MANAGER,
        }

    def _on_manage_classes(self) -> None:
        if not self._can_manage_class_assignments():
            self._notification_service.notify(
                "Only Admin or Manager accounts can manage teacher class assignments.",
                "warning",
            )
            return
        if self._current_teacher is None or self._current_teacher_id is None:
            return
        if self._current_teacher.deleted_at is not None:
            self._notification_service.notify(
                "Archived teachers must be restored before managing classes.", "warning"
            )
            return

        dialog = TeacherAssignmentDialog(
            assignment_service=self._assignment_service,
            teacher_id=self._current_teacher_id,
            collaboration_manager=self._collaboration_manager,
            notification_service=self._notification_service,
            teacher_is_active=(
                self._current_teacher.status == Teacher.STATUS_ACTIVE
            ),
            parent=self,
        )
        dialog.assignments_changed.connect(self._on_assignment_changed)
        dialog.exec()

    def _on_assignment_changed(self) -> None:
        if self._current_teacher_id:
            self.load_teacher(self._current_teacher_id)
            self.teacher_updated.emit()

    def _on_restore(self) -> None:
        if self._current_teacher_id is None:
            return
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(
                "You must be in WRITE mode to restore a teacher.", "warning"
            )
            return
        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            "Restore this teacher?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._teacher_service.restore_teacher(self._current_teacher_id)
            self.load_teacher(self._current_teacher_id)
            self.teacher_updated.emit()
            self._notification_service.notify("Teacher restored successfully.", "success")
        except Exception:
            logger.exception("Restore teacher failed")
            QMessageBox.critical(self, "Error", "Failed to restore teacher.")

    def _on_edit(self) -> None:
        if self._current_teacher_id is None:
            return
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to edit.", "warning")
            return
        dialog = TeacherFormDialog(self._teacher_service, self._current_teacher_id, parent=self)
        if dialog.exec() == TeacherFormDialog.DialogCode.Accepted:
            self.load_teacher(self._current_teacher_id)
            self.teacher_updated.emit()

    def _on_data_changed(self) -> None:
        if self._current_teacher_id:
            self.load_teacher(self._current_teacher_id)
            self.teacher_updated.emit()

    def set_write_enabled(self, enabled: bool) -> None:
        if self._current_teacher is None:
            self.edit_btn.setEnabled(enabled)
            if hasattr(self, "manage_classes_btn"):
                self.manage_classes_btn.setEnabled(enabled and self._can_manage_class_assignments())
        else:
            archived = self._current_teacher.deleted_at is not None
            self.edit_btn.setEnabled(enabled and not archived)
            if hasattr(self, "manage_classes_btn"):
                # Keep lifecycle/write-state semantics explicit, then apply
                # the additional role authorization layer.
                self.manage_classes_btn.setEnabled(enabled and not archived)
                if self.manage_classes_btn.isEnabled():
                    self.manage_classes_btn.setEnabled(
                        self._can_manage_class_assignments()
                    )
            if hasattr(self, "restore_btn"):
                self.restore_btn.setEnabled(enabled and archived)
        # Documents upload button is inside documents_widget, need to propagate
        if hasattr(self.documents_widget, 'set_write_enabled'):
            self.documents_widget.set_write_enabled(enabled)