# -*- coding: utf-8 -*-
"""
ClassListPage - list of classes with search, filter, CRUD.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QMessageBox, QMenu, QSizePolicy
)
from PySide6.QtGui import QAction

from centermanager.models.class_ import Class
from centermanager.services.class_service import ClassService
from centermanager.services.class_timeline_service import ClassTimelineService
from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.ui.design_system import (
    SearchBar, EmptyState, PrimaryButton, SecondaryButton
)
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget
from centermanager.ui.class_workspace.class_form_dialog import ClassFormDialog
from centermanager.ui.class_workspace.class_detail_page import ClassDetailPage


logger = logging.getLogger(__name__)


class ClassListPage(QWidget):
    class_selected = Signal(int)

    def __init__(
        self,
        class_service: ClassService,
        assignment_service: TeacherAssignmentService,
        timeline_service: ClassTimelineService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._class_service = class_service
        self._assignment_service = assignment_service
        self._timeline_service = timeline_service
        self._classes: List[Class] = []
        self._filtered: List[Class] = []
        self._sort_key: Optional[str] = None
        self._sort_asc: bool = True
        self._selected_ids: List[int] = []

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

        self.search_bar = SearchBar("Search by name, course, teacher...")
        self.search_bar.text_changed.connect(self._on_search)
        top_row.addWidget(self.search_bar)

        self.refresh_btn = SecondaryButton("🔄 Refresh")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)

        self.add_btn = PrimaryButton("+ Add Class")
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
            {"key": "name", "label": "Class", "sortable": True},
            {"key": "course", "label": "Course", "sortable": True},
            {"key": "teacher_names", "label": "Teacher", "sortable": False},
            {"key": "student_count", "label": "Students", "sortable": False},
            {"key": "status", "label": "Status", "sortable": True},
            {"key": "schedule", "label": "Schedule", "sortable": False},
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
            self._classes = self._class_service.list_classes()
            self._apply_filters_and_sort()
        except Exception as e:
            logger.exception("Failed to refresh class list")
            QMessageBox.critical(self, "Error", "Failed to load classes.")
        finally:
            self.loading.setVisible(False)

    def _apply_filters_and_sort(self) -> None:
        filtered = self._filter_classes(self.search_bar.text())
        if self._sort_key:
            filtered.sort(key=lambda c: getattr(c, self._sort_key, ""), reverse=not self._sort_asc)
        self._filtered = filtered
        self._populate_table()

    def _filter_classes(self, text: str) -> List[Class]:
        if not text.strip():
            return self._classes[:]
        try:
            return self._class_service.search_classes(text.strip())
        except Exception:
            lower = text.strip().lower()
            return [c for c in self._classes
                    if lower in c.name.lower() or lower in (c.course or "").lower()]

    def _populate_table(self) -> None:
        data = []
        for c in self._filtered:
            teacher_names = ", ".join([t.full_name for t in c.teachers]) if c.teachers else "-"
            schedule = f"{c.start_date.strftime('%d/%m/%Y') if c.start_date else ''} - {c.end_date.strftime('%d/%m/%Y') if c.end_date else ''}"
            data.append({
                "name": c.name,
                "course": c.course or "-",
                "teacher_names": teacher_names,
                "student_count": str(c.student_count),
                "status": c.status or "ACTIVE",
                "schedule": schedule,
                "_id": c.id,
            })
        self.data_table.set_data(data, len(data))

    def _on_search(self, text: str) -> None:
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
        self.bulk_bar.setVisible(count > 0)
        self.bulk_count_label.setText(f"{count} selected")

    def _clear_selection(self) -> None:
        self.data_table.clear_selection()
        self._selected_ids = []
        self._update_bulk_bar()

    def _bulk_archive(self) -> None:
        if not self._selected_ids:
            return
        reply = QMessageBox.question(
            self, "Confirm Archive",
            f"Archive {len(self._selected_ids)} classes?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                for cid in self._selected_ids:
                    self._class_service.archive_class(cid)
                self._clear_selection()
                self.refresh()
            except Exception as e:
                logger.exception("Bulk archive failed")
                QMessageBox.critical(self, "Error", "Failed to archive classes.")

    def _on_row_double_clicked(self, row: int) -> None:
        if row < len(self._filtered):
            self.class_selected.emit(self._filtered[row].id)

    def _on_context_menu(self, pos, row: int) -> None:
        if row < 0 or row >= len(self._filtered):
            return
        class_obj = self._filtered[row]
        menu = QMenu(self)
        view_action = QAction("View Class", self)
        view_action.triggered.connect(lambda: self.class_selected.emit(class_obj.id))
        menu.addAction(view_action)

        edit_action = QAction("Edit Class", self)
        edit_action.triggered.connect(lambda: self._edit_class(class_obj.id))
        menu.addAction(edit_action)

        menu.addSeparator()
        archive_action = QAction("Archive Class", self)
        archive_action.triggered.connect(lambda: self._archive_class(class_obj.id))
        menu.addAction(archive_action)

        menu.exec(pos)

    def _edit_class(self, class_id: int) -> None:
        dialog = ClassFormDialog(self._class_service, class_id=class_id, parent=self)
        if dialog.exec() == ClassFormDialog.DialogCode.Accepted:
            self.refresh()

    def _archive_class(self, class_id: int) -> None:
        reply = QMessageBox.question(
            self, "Confirm Archive",
            "Archive this class?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._class_service.archive_class(class_id)
                self.refresh()
            except Exception as e:
                logger.exception("Archive failed")
                QMessageBox.critical(self, "Error", "Failed to archive class.")

    def show_add_dialog(self) -> None:
        dialog = ClassFormDialog(self._class_service, parent=self)
        if dialog.exec() == ClassFormDialog.DialogCode.Accepted:
            self.refresh()