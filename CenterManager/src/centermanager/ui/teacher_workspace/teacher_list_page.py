# -*- coding: utf-8 -*-
"""
TeacherListPage - list of teachers with search, filter, CRUD.
Now with collaboration support.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QComboBox, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QMessageBox, QMenu, QSizePolicy
)
from PySide6.QtGui import QAction

from centermanager.models.teacher import Teacher
from centermanager.services.teacher_service import TeacherService
from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.services.teacher_document_service import TeacherDocumentService
from centermanager.services.teacher_timeline_service import TeacherTimelineService
from centermanager.ui.design_system import (
    SearchBar, EmptyState, PrimaryButton, SecondaryButton
)
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget
from centermanager.ui.teacher_workspace.teacher_form_dialog import TeacherFormDialog
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService


logger = logging.getLogger(__name__)


class TeacherListPage(QWidget):
    teacher_selected = Signal(int)
    teacher_changed = Signal()

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
        self._teachers: List[Teacher] = []
        self._filtered: List[Teacher] = []
        self._sort_key: Optional[str] = None
        self._sort_asc: bool = True
        self._selected_ids: List[int] = []
        self._status_filter: str = "ACTIVE"
        self._assignment_filter: str = "ALL"

        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(f"""
            background: {COLORS['surface']};
            padding: {SPACING['sm']}px {SPACING['md']}px;
            border-bottom: 1px solid {COLORS['border_light']};
        """)
        toolbar_layout = QVBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(SPACING['xs'])

        top_row = QHBoxLayout()
        top_row.setSpacing(SPACING['sm'])

        self.search_bar = SearchBar("Search by code, name, phone, email...")
        self.search_bar.text_changed.connect(self._on_search)
        top_row.addWidget(self.search_bar)

        self.status_filter = QComboBox()
        self.status_filter.addItem("Active", "ACTIVE")
        self.status_filter.addItem("Inactive", "INACTIVE")
        self.status_filter.addItem("Archived", "ARCHIVED")
        self.status_filter.addItem("All Current", "ALL")
        self.status_filter.currentIndexChanged.connect(self._on_status_filter_changed)
        self.status_filter.setMinimumWidth(130)
        top_row.addWidget(self.status_filter)

        self.assignment_filter = QComboBox()
        self.assignment_filter.addItem("All Assignments", "ALL")
        self.assignment_filter.addItem("Has Classes", "ASSIGNED")
        self.assignment_filter.addItem("No Classes", "UNASSIGNED")
        self.assignment_filter.currentIndexChanged.connect(self._on_assignment_filter_changed)
        self.assignment_filter.setMinimumWidth(150)
        top_row.addWidget(self.assignment_filter)

        self.refresh_btn = SecondaryButton("🔄 Refresh")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)

        self.add_btn = PrimaryButton("+ Add Teacher")
        self.add_btn.setFixedHeight(34)
        self.add_btn.clicked.connect(self.show_add_dialog)
        top_row.addWidget(self.add_btn)

        toolbar_layout.addLayout(top_row)
        layout.addWidget(toolbar)

        # Bulk actions bar
        self.bulk_bar = QWidget()
        self.bulk_bar.setStyleSheet(f"""
            background: {COLORS['primary_hover']};
            padding: {SPACING['xs']}px {SPACING['md']}px;
            border-bottom: 1px solid {COLORS['border_light']};
        """)
        self.bulk_bar.setVisible(False)
        bulk_layout = QHBoxLayout(self.bulk_bar)
        bulk_layout.setContentsMargins(0, 0, 0, 0)
        self.bulk_count_label = QLabel("0 selected")
        self.bulk_count_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-weight: 500;")
        bulk_layout.addWidget(self.bulk_count_label)
        bulk_layout.addStretch()
        self.bulk_archive_btn = QPushButton("Archive Selected")
        self.bulk_archive_btn.setStyleSheet(f"color: {COLORS['danger']};")
        self.bulk_archive_btn.clicked.connect(self._bulk_archive)
        bulk_layout.addWidget(self.bulk_archive_btn)
        self.bulk_clear_btn = QPushButton("Clear")
        self.bulk_clear_btn.clicked.connect(self._clear_selection)
        bulk_layout.addWidget(self.bulk_clear_btn)
        layout.addWidget(self.bulk_bar)

        # Data Table
        columns = [
            {"key": "teacher_code", "label": "Code", "sortable": True},
            {"key": "full_name", "label": "Name", "sortable": True},
            {"key": "phone", "label": "Phone", "sortable": True},
            {"key": "email", "label": "Email", "sortable": True},
            {"key": "status", "label": "Status", "sortable": True},
            {"key": "classes", "label": "Assigned Classes", "sortable": False},
        ]
        self.data_table = DataTable(columns, page_size=20)
        self.data_table.sort_requested.connect(self._on_sort)
        self.data_table.selection_changed.connect(self._on_selection_changed)
        self.data_table.row_double_clicked.connect(self._on_row_double_clicked)
        self.data_table.context_menu_requested.connect(self._on_context_menu)
        layout.addWidget(self.data_table)

        self.loading = LoadingWidget()
        self.loading.setVisible(False)
        layout.addWidget(self.loading)

    def refresh(self) -> None:
        self.loading.setVisible(True)
        try:
            if self._status_filter == "ARCHIVED":
                self._teachers = self._teacher_service.list_archived_teachers()
            else:
                self._teachers = self._teacher_service.list_teachers()
            self._clear_selection()
            self._apply_filters_and_sort()
        except Exception as e:
            logger.exception("Failed to refresh teacher list")
            QMessageBox.critical(self, "Error", "Failed to load teachers.")
        finally:
            self.loading.setVisible(False)

    def _apply_filters_and_sort(self) -> None:
        filtered = self._filter_teachers(self.search_bar.text())
        if self._sort_key:
            filtered.sort(key=lambda t: getattr(t, self._sort_key, ""), reverse=not self._sort_asc)
        self._filtered = filtered
        self._populate_table()

    def _filter_teachers(self, text: str) -> List[Teacher]:
        teachers = self._teachers[:]

        if self._status_filter == "ACTIVE":
            teachers = [t for t in teachers if t.status == Teacher.STATUS_ACTIVE]
        elif self._status_filter == "INACTIVE":
            teachers = [t for t in teachers if t.status == Teacher.STATUS_INACTIVE]

        if self._assignment_filter == "ASSIGNED":
            teachers = [t for t in teachers if bool(t.assigned_classes)]
        elif self._assignment_filter == "UNASSIGNED":
            teachers = [t for t in teachers if not bool(t.assigned_classes)]

        if not text.strip():
            return teachers

        lower = text.strip().lower()
        return [
            t for t in teachers
            if lower in (t.teacher_code or "").lower()
            or lower in (t.full_name or "").lower()
            or lower in (t.phone or "").lower()
            or lower in (t.email or "").lower()
        ]

    def _populate_table(self) -> None:
        data = []
        for t in self._filtered:
            classes = ", ".join([c.name for c in t.assigned_classes]) if t.assigned_classes else "-"
            data.append({
                "teacher_code": t.teacher_code,
                "full_name": t.full_name,
                "phone": t.phone or "-",
                "email": t.email or "-",
                "status": "ARCHIVED" if t.deleted_at is not None else (t.status or "-"),
                "classes": classes,
                "_id": t.id,
            })
        self.data_table.set_data(data, len(data))

    def _on_search(self, text: str) -> None:
        self._apply_filters_and_sort()

    def _on_status_filter_changed(self) -> None:
        self._status_filter = self.status_filter.currentData()
        archived = self._status_filter == "ARCHIVED"
        self.assignment_filter.setEnabled(not archived)
        self.add_btn.setEnabled(not archived)
        self.refresh()

    def _on_assignment_filter_changed(self) -> None:
        self._assignment_filter = self.assignment_filter.currentData()
        self._apply_filters_and_sort()

    def _on_sort(self, key: str, ascending: bool) -> None:
        self._sort_key = key
        self._sort_asc = ascending
        self._apply_filters_and_sort()

    def _on_selection_changed(self, indices: List[int]) -> None:
        self._selected_ids = []
        for idx in indices:
            if idx < len(self._filtered):
                self._selected_ids.append(self._filtered[idx].id)
        self._update_bulk_bar()

    def _update_bulk_bar(self) -> None:
        count = len(self._selected_ids)
        can_archive = self._status_filter != "ARCHIVED"
        self.bulk_bar.setVisible(count > 0 and can_archive)
        self.bulk_count_label.setText(f"{count} selected")

    def _clear_selection(self) -> None:
        self.data_table.clear_selection()
        self._selected_ids = []
        self._update_bulk_bar()

    def _bulk_archive(self) -> None:
        if not self._selected_ids:
            return
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to archive teachers.", "warning")
            return
        reply = QMessageBox.question(
            self, "Confirm Archive",
            f"Archive {len(self._selected_ids)} teachers?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                for tid in self._selected_ids:
                    self._teacher_service.delete_teacher(tid)
                self._clear_selection()
                self.refresh()
                self.teacher_changed.emit()
            except Exception as e:
                logger.exception("Bulk archive failed")
                QMessageBox.critical(self, "Error", "Failed to archive teachers.")

    def _on_row_double_clicked(self, row: int) -> None:
        if row < len(self._filtered):
            self.teacher_selected.emit(self._filtered[row].id)

    def _on_context_menu(self, pos, row: int) -> None:
        if row < 0 or row >= len(self._filtered):
            return
        teacher = self._filtered[row]
        menu = QMenu(self)
        view_action = QAction("View Teacher", self)
        view_action.triggered.connect(lambda: self.teacher_selected.emit(teacher.id))
        menu.addAction(view_action)

        if teacher.deleted_at is not None:
            restore_action = QAction("Restore Teacher", self)
            restore_action.triggered.connect(lambda: self._restore_teacher(teacher.id))
            menu.addAction(restore_action)
        else:
            edit_action = QAction("Edit Teacher", self)
            edit_action.triggered.connect(lambda: self._edit_teacher(teacher.id))
            menu.addAction(edit_action)

            menu.addSeparator()
            archive_action = QAction("Archive Teacher", self)
            archive_action.triggered.connect(lambda: self._archive_teacher(teacher.id))
            menu.addAction(archive_action)

        menu.exec(pos)

    def _restore_teacher(self, teacher_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(
                "You must be in WRITE mode to restore a teacher.", "warning"
            )
            return
        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            "Restore this teacher? The teacher will return to the current teacher list.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        try:
            self._teacher_service.restore_teacher(teacher_id)
            self.refresh()
            self.teacher_changed.emit()
            self._notification_service.notify("Teacher restored successfully.", "success")
        except Exception:
            logger.exception("Restore teacher failed")
            QMessageBox.critical(self, "Error", "Failed to restore teacher.")

    def _edit_teacher(self, teacher_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to edit.", "warning")
            return
        dialog = TeacherFormDialog(self._teacher_service, teacher_id=teacher_id, parent=self)
        if dialog.exec() == TeacherFormDialog.DialogCode.Accepted:
            self.refresh()
            self.teacher_changed.emit()

    def _archive_teacher(self, teacher_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to archive.", "warning")
            return
        reply = QMessageBox.question(
            self, "Confirm Archive",
            "Archive this teacher?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._teacher_service.delete_teacher(teacher_id)
                self.refresh()
                self.teacher_changed.emit()
            except Exception as e:
                logger.exception("Archive failed")
                QMessageBox.critical(self, "Error", "Failed to archive teacher.")

    def show_add_dialog(self) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to add a teacher.", "warning")
            return
        dialog = TeacherFormDialog(self._teacher_service, parent=self)
        if dialog.exec() == TeacherFormDialog.DialogCode.Accepted:
            self.refresh()
            self.teacher_changed.emit()

    def set_write_enabled(self, enabled: bool) -> None:
        self.add_btn.setEnabled(enabled and self._status_filter != "ARCHIVED")
        self.bulk_archive_btn.setEnabled(enabled and self._status_filter != "ARCHIVED")