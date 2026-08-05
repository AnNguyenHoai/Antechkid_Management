# -*- coding: utf-8 -*-
"""StudentListPage - Enterprise data management screen."""
import logging
from typing import Optional, List, Dict, Any

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QMessageBox, QMenu, QSizePolicy
)
from PySide6.QtGui import QAction

from centermanager.models.student import Student
from centermanager.services.student_service import StudentService
from centermanager.services.parent_service import ParentService
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.student_filter_service import StudentFilterService
from centermanager.services.student_import_service import StudentImportService
from centermanager.services.student_export_service import StudentExportService
from centermanager.ui.design_system import (
    Avatar, SearchBar, EmptyState, PrimaryButton, SecondaryButton,
    FilterBar
)
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.students.student_filter_dialog import StudentFilterDialog
from centermanager.ui.students.student_import_dialog import StudentImportDialog

# NEW imports for collaboration
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService

logger = logging.getLogger(__name__)


class StudentListPage(QWidget):
    student_selected = Signal(int)
    data_updated = Signal()
    filter_clicked = Signal()

    def __init__(
        self,
        student_service: StudentService,
        parent_service: ParentService,
        assessment_service: AssessmentService,
        filter_service: StudentFilterService,
        import_service: StudentImportService,
        export_service: StudentExportService,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._student_service = student_service
        self._parent_service = parent_service
        self._assessment_service = assessment_service
        self._filter_service = filter_service
        self._import_service = import_service
        self._export_service = export_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._students: List[Student] = []
        self._filtered: List[Student] = []
        self._sort_key: Optional[str] = None
        self._sort_asc: bool = True
        self._selected_ids: List[int] = []

        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

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

        self.search_bar = SearchBar()
        self.search_bar.setPlaceholderText("Search by code, name, parent phone, parent name...")
        self.search_bar.text_changed.connect(self._on_search)
        top_row.addWidget(self.search_bar)

        self.filter_btn = SecondaryButton("🔍 Filter")
        self.filter_btn.setFixedHeight(34)
        self.filter_btn.clicked.connect(self.filter_clicked.emit)
        top_row.addWidget(self.filter_btn)

        self.refresh_btn = SecondaryButton("🔄 Refresh")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.clicked.connect(self.refresh)
        top_row.addWidget(self.refresh_btn)

        self.add_btn = PrimaryButton("+ Add")
        self.add_btn.setFixedHeight(34)
        self.add_btn.clicked.connect(self.show_add_dialog)
        top_row.addWidget(self.add_btn)

        self.import_btn = SecondaryButton("📥 Import")
        self.import_btn.setFixedHeight(34)
        self.import_btn.clicked.connect(self.show_import_dialog)
        top_row.addWidget(self.import_btn)

        self.export_btn = SecondaryButton("📤 Export")
        self.export_btn.setFixedHeight(34)
        self.export_btn.clicked.connect(self.export_students)
        top_row.addWidget(self.export_btn)

        toolbar_layout.addLayout(top_row)

        self.filter_bar = FilterBar([
            {"key": "status", "label": "Status", "type": "combo", "options": ["Active", "Archived"]},
            {"key": "enrollment", "label": "Enrollment", "type": "combo", "options": ["Enrolled", "Not Enrolled"]},
            {"key": "assessment", "label": "Assessment", "type": "combo", "options": ["Has Assessment", "No Assessment"]},
        ])
        self.filter_bar.filter_changed.connect(self._on_filter_changed)
        toolbar_layout.addWidget(self.filter_bar)

        layout.addWidget(toolbar)

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
        self.bulk_delete_btn = QPushButton("Delete Selected")
        self.bulk_delete_btn.setStyleSheet(f"color: {COLORS['danger']};")
        self.bulk_delete_btn.clicked.connect(self._bulk_delete)
        bulk_layout.addWidget(self.bulk_delete_btn)
        self.bulk_export_btn = QPushButton("Export Selected")
        self.bulk_export_btn.clicked.connect(self._bulk_export)
        bulk_layout.addWidget(self.bulk_export_btn)
        self.bulk_clear_btn = QPushButton("Clear")
        self.bulk_clear_btn.clicked.connect(self._clear_selection)
        bulk_layout.addWidget(self.bulk_clear_btn)
        layout.addWidget(self.bulk_bar)

        columns = [
            {"key": "student_code", "label": "Code", "sortable": True},
            {"key": "full_name", "label": "Name", "sortable": True},
            {"key": "status", "label": "Status", "sortable": True},
            {"key": "current_level", "label": "Level", "sortable": True},
            {"key": "created_at", "label": "Created", "sortable": True},
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
            self._students = self._student_service.list_students()
            self._apply_filters_and_sort()
        except Exception as e:
            logger.exception("Failed to refresh student list")
            QMessageBox.critical(self, "Error", "Failed to load students.")
        finally:
            self.loading.setVisible(False)
        # Emit data_updated để dashboard refresh
        self.data_updated.emit()

    def _apply_filters_and_sort(self) -> None:
        filtered = self._filter_students(self.search_bar.text())
        if self._sort_key:
            filtered.sort(key=lambda s: getattr(s, self._sort_key, ""), reverse=not self._sort_asc)
        self._filtered = filtered
        self._populate_table()

    def _filter_students(self, text: str) -> List[Student]:
        if not text.strip():
            return self._students[:]
        try:
            return self._student_service.search_students(text.strip())
        except Exception:
            lower = text.strip().lower()
            return [s for s in self._students
                    if lower in s.student_code.lower() or lower in s.full_name.lower()]

    def _populate_table(self) -> None:
        data = []
        for s in self._filtered:
            data.append({
                "student_code": s.student_code,
                "full_name": s.full_name,
                "status": s.status or "",
                "current_level": s.current_level or "",
                "created_at": s.created_at.strftime("%d/%m/%Y"),
                "_id": s.id,
            })
        self.data_table.set_data(data, len(data))
        self.data_updated.emit()

    def _on_search(self, text: str) -> None:
        self._apply_filters_and_sort()

    def _on_filter_changed(self, filters: Dict[str, str]) -> None:
        from centermanager.dto.student_filter_dto import StudentFilter
        status_map = {"Active": "ACTIVE", "Archived": "ARCHIVED"}
        enrollment_map = {"Enrolled": "enrolled", "Not Enrolled": "not_enrolled"}
        assessment_map = {"Has Assessment": "has_assessment", "No Assessment": "no_assessment"}

        filter_dto = StudentFilter(
            status=status_map.get(filters.get("status", ""), None),
            enrollment_status=enrollment_map.get(filters.get("enrollment", ""), None),
            assessment_status=assessment_map.get(filters.get("assessment", ""), None),
        )
        try:
            self._filtered = self._filter_service.filter_students(filter_dto)
            self._apply_filters_and_sort()
        except Exception as e:
            logger.exception("Filter failed")
            QMessageBox.critical(self, "Filter Error", str(e))

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

    def _bulk_delete(self) -> None:
        if not self._selected_ids:
            return
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to delete students.", "warning")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete {len(self._selected_ids)} students?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                for sid in self._selected_ids:
                    self._student_service.delete_student(sid)
                self._clear_selection()
                self.refresh()
            except Exception as e:
                logger.exception("Bulk delete failed")
                QMessageBox.critical(self, "Error", "Failed to delete students.")

    def _bulk_export(self) -> None:
        if not self._selected_ids:
            return
        # Export is read-only, no need to check write.
        try:
            students = [self._student_service.get_student(sid) for sid in self._selected_ids]
            file_path = self._export_service.export_csv(students)
            QMessageBox.information(self, "Export", f"Exported {len(students)} students to {file_path}")
        except Exception as e:
            logger.exception("Bulk export failed")
            QMessageBox.critical(self, "Error", "Failed to export students.")

    def _on_row_double_clicked(self, row: int) -> None:
        if row < len(self._filtered):
            self.student_selected.emit(self._filtered[row].id)

    def _on_context_menu(self, pos, row: int) -> None:
        if row < 0 or row >= len(self._filtered):
            return
        student = self._filtered[row]
        menu = QMenu(self)
        view_action = QAction("View Student", self)
        view_action.triggered.connect(lambda: self.student_selected.emit(student.id))
        menu.addAction(view_action)

        edit_action = QAction("Edit Student", self)
        edit_action.triggered.connect(lambda: self._edit_student(student.id))
        menu.addAction(edit_action)

        menu.addSeparator()
        delete_action = QAction("Delete Student", self)
        delete_action.triggered.connect(lambda: self._delete_student(student.id))
        menu.addAction(delete_action)

        menu.exec(pos)

    def _edit_student(self, student_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to edit.", "warning")
            return
        dialog = StudentFormDialog(self._student_service, student_id=student_id, parent=self)
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self.refresh()

    def _delete_student(self, student_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to delete.", "warning")
            return
        reply = QMessageBox.question(
            self, "Confirm Delete",
            "Delete this student?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._student_service.delete_student(student_id)
                self.refresh()
            except Exception as e:
                logger.exception("Delete failed")
                QMessageBox.critical(self, "Error", "Failed to delete student.")

    def show_add_dialog(self) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to add a student.", "warning")
            return
        dialog = StudentFormDialog(self._student_service, parent=self)
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self.refresh()

    def show_import_dialog(self) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to import.", "warning")
            return
        dialog = StudentImportDialog(self._import_service, parent=self)
        if dialog.exec() == StudentImportDialog.DialogCode.Accepted:
            self.refresh()

    def export_students(self) -> None:
        # Export is read-only, no write check needed.
        try:
            file_path = self._export_service.export_all_active()
            QMessageBox.information(self, "Export", f"Exported to: {file_path}")
        except Exception as e:
            logger.exception("Export failed")
            QMessageBox.critical(self, "Export Error", str(e))

    def show_filter_dialog(self) -> None:
        dialog = StudentFilterDialog(parent=self)
        if dialog.exec() == StudentFilterDialog.DialogCode.Accepted:
            filter_criteria = dialog.get_filter()
            if filter_criteria:
                try:
                    self._filtered = self._filter_service.filter_students(filter_criteria)
                    self._populate_table()
                except Exception as e:
                    QMessageBox.critical(self, "Filter Error", str(e))

    # ====== NEW: Collaboration method ======
    def set_write_enabled(self, enabled: bool) -> None:
        self.add_btn.setEnabled(enabled)
        self.import_btn.setEnabled(enabled)
        self.bulk_delete_btn.setEnabled(enabled)
        # Export is read-only, keep enabled
        # Filter, refresh, search, etc. are read-only, keep enabled