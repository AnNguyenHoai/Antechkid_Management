# -*- coding: utf-8 -*-
"""StudentListPage - production data-heavy student management screen."""

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QMenu, QMessageBox, QVBoxLayout, QWidget

from centermanager.models.student import Student
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.parent_service import ParentService
from centermanager.services.student_export_service import StudentExportService
from centermanager.services.student_filter_service import StudentFilterService
from centermanager.services.student_import_service import StudentImportService
from centermanager.services.student_service import StudentService
from centermanager.ui.design_system.foundation import ButtonVariant, Toolbar
from centermanager.ui.design_system.tokens import SPACING
from centermanager.ui.shared import (
    BulkActionBar,
    DataTable,
    SearchToolbar,
    TableDensity,
)
from centermanager.ui.students.student_filter_dialog import StudentFilterDialog
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.students.student_import_dialog import StudentImportDialog

from centermanager.platform.business import PermissionGuard, WriteGuard
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.context import PlatformContext
from centermanager.ui.workspace_base import WorkspaceBase

logger = logging.getLogger(__name__)


class StudentListPage(WorkspaceBase):
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
        platform_context: PlatformContext,
        collaboration_manager: CollaborationManager,
        notification_service,
        parent: Optional[QWidget] = None,
    ):
        self._student_service = student_service
        self._parent_service = parent_service
        self._assessment_service = assessment_service
        self._filter_service = filter_service
        self._import_service = import_service
        self._export_service = export_service
        self._notification_service = notification_service

        super().__init__(
            workspace_id="student_list",
            platform_context=platform_context,
            collaboration_manager=collaboration_manager,
            parent=parent,
        )

        self._students: List[Student] = []
        self._filtered: List[Student] = []
        self._sort_key: Optional[str] = None
        self._sort_asc: bool = True
        self._selected_ids: List[int] = []

        self._setup_ui()
        self.refresh()
        self._is_initialized = True

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = Toolbar(self)
        self.search_bar = SearchToolbar(
            placeholder="Search by code, name, parent phone, parent name...",
            filters=[
                {
                    "key": "status",
                    "label": "Status",
                    "options": ["Active", "Archived", "Deleted"],
                },
                {
                    "key": "enrollment",
                    "label": "Enrollment",
                    "options": ["Enrolled", "Not Enrolled"],
                },
                {
                    "key": "assessment",
                    "label": "Assessment",
                    "options": ["Has Assessment", "No Assessment"],
                },
            ],
            parent=toolbar,
        )
        self.search_bar.search_changed.connect(self._on_search)
        self.search_bar.filters_changed.connect(self._on_filter_changed)
        # Compatibility alias for older workspace code that referred to the
        # separate FilterBar. V2 intentionally owns search + filters together.
        self.filter_bar = self.search_bar
        toolbar.add_widget(self.search_bar, align="start")

        self.filter_btn = toolbar.add_action(
            "More filters",
            self.filter_clicked.emit,
            variant=ButtonVariant.SECONDARY,
        )
        self.refresh_btn = toolbar.add_action(
            "Refresh",
            self.refresh,
            variant=ButtonVariant.SECONDARY,
        )
        self.import_btn = toolbar.add_action(
            "Import",
            self.show_import_dialog,
            variant=ButtonVariant.SECONDARY,
        )
        self.export_btn = toolbar.add_action(
            "Export",
            self.export_students,
            variant=ButtonVariant.SECONDARY,
        )
        self.add_btn = toolbar.add_action(
            "Add student",
            self.show_add_dialog,
            variant=ButtonVariant.PRIMARY,
        )
        layout.addWidget(toolbar)

        self.bulk_bar = BulkActionBar(self)
        self.bulk_delete_btn = self.bulk_bar.add_action(
            "delete",
            "Delete selected",
            self._bulk_delete,
            variant=ButtonVariant.DANGER,
        )
        self.bulk_export_btn = self.bulk_bar.add_action(
            "export",
            "Export selected",
            self._bulk_export,
            variant=ButtonVariant.SECONDARY,
        )
        self.bulk_bar.clear_requested.connect(self._clear_selection)
        # Compatibility aliases retained for tests/integrations that inspect
        # these controls directly.
        self.bulk_count_label = self.bulk_bar.count_label
        self.bulk_clear_btn = self.bulk_bar.clear_button
        layout.addWidget(self.bulk_bar)

        columns = [
            {"key": "student_code", "label": "Code", "sortable": True},
            {"key": "full_name", "label": "Name", "sortable": True},
            {"key": "status", "label": "Status", "sortable": True},
            {"key": "current_level", "label": "Level", "sortable": True},
            {"key": "created_at", "label": "Created", "sortable": True},
        ]
        self.data_table = DataTable(
            columns,
            page_size=20,
            density=TableDensity.COMPACT,
            empty_title="No students found",
            empty_message="Try changing search or filters, then refresh the list.",
        )
        self.data_table.sort_requested.connect(self._on_sort)
        self.data_table.selection_changed.connect(self._on_selection_changed)
        self.data_table.row_double_clicked.connect(self._on_row_double_clicked)
        self.data_table.context_menu_requested.connect(self._on_context_menu)
        layout.addWidget(self.data_table, 1)

        # Compatibility reference: loading is now rendered inline by DataTable.
        self.loading = self.data_table.loading_state

        self._update_button_states()

    def _update_button_states(self) -> None:
        """Update button states based on write permission."""
        can_write = self.can_write()
        self.add_btn.setEnabled(can_write)
        self.import_btn.setEnabled(can_write)
        self.bulk_delete_btn.setEnabled(can_write)

    def initialize(self) -> None:
        pass

    def refresh(self) -> None:
        self.data_table.set_loading(True)
        self._selected_ids = []
        self._update_bulk_bar()
        try:
            self._students = self._student_service.list_students()
            self._filtered_base = self._students[:]
            self._apply_filters_and_sort()
        except Exception:
            logger.exception("Failed to refresh student list")
            self.data_table.set_error(
                "Student records could not be loaded.",
                title="Unable to load students",
                retry_callback=self.refresh,
            )
            QMessageBox.critical(self, "Error", "Failed to load students.")
        self.data_updated.emit()
        self._update_button_states()

    def show_add_dialog(self) -> None:
        try:
            self.require_write()
        except Exception as e:
            QMessageBox.warning(self, "Permission Denied", str(e))
            return

        dialog = StudentFormDialog(self._student_service, parent=self)
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self.refresh()

    def _apply_filters_and_sort(self) -> None:
        filtered = self._filter_students(self.search_bar.text())
        if self._sort_key:
            filtered.sort(
                key=lambda s: getattr(s, self._sort_key, ""),
                reverse=not self._sort_asc,
            )
        self._filtered = filtered
        self._populate_table()

    def _filter_students(self, text: str) -> List[Student]:
        """Search over the current lifecycle-filtered result set."""
        base = getattr(self, "_filtered_base", self._students)
        if not text.strip():
            return base[:]

        lower = text.strip().lower()
        results = []
        for student in base:
            student_code = (student.student_code or "").lower()
            full_name = (student.full_name or "").lower()
            if lower in student_code or lower in full_name:
                results.append(student)
                continue

            try:
                parents = self._parent_service.get_parents_by_student(student.id)
            except Exception:
                parents = []

            for parent in parents or []:
                parent_name = (
                    getattr(parent, "full_name", None)
                    or getattr(parent, "name", None)
                    or ""
                ).lower()
                parent_phone = (getattr(parent, "phone", None) or "").lower()
                if lower in parent_name or lower in parent_phone:
                    results.append(student)
                    break
        return results

    def _populate_table(self) -> None:
        data = []
        for student in self._filtered:
            data.append(
                {
                    "student_code": student.student_code,
                    "full_name": student.full_name,
                    "status": student.status or "",
                    "current_level": student.current_level or "",
                    "created_at": student.created_at.strftime("%d/%m/%Y"),
                    "_id": student.id,
                }
            )
        self.data_table.set_data(data, len(data))
        if not data:
            self.data_table.setToolTip(
                "No students match the current search and filters. Clear filters or refresh the list."
            )
        else:
            self.data_table.setToolTip("")
        self.data_updated.emit()

    def _on_search(self, text: str) -> None:
        self._apply_filters_and_sort()

    def _on_filter_changed(self, filters: Dict[str, str]) -> None:
        from centermanager.dto.student_filter_dto import StudentFilter

        status_map = {
            "Active": "ACTIVE",
            "Archived": "ARCHIVED",
            "Deleted": "DELETED",
        }
        enrollment_map = {
            "Enrolled": "enrolled",
            "Not Enrolled": "not_enrolled",
        }
        assessment_map = {
            "Has Assessment": "has_assessment",
            "No Assessment": "no_assessment",
        }

        filter_dto = StudentFilter(
            status=status_map.get(filters.get("status", ""), None),
            enrollment_status=enrollment_map.get(filters.get("enrollment", ""), None),
            assessment_status=assessment_map.get(filters.get("assessment", ""), None),
        )
        try:
            self._filtered_base = self._filter_service.filter_students(filter_dto)
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
        for visible_row in indices:
            data_index = self.data_table.data_index_for_visible_row(visible_row)
            if 0 <= data_index < len(self._filtered):
                self._selected_ids.append(self._filtered[data_index].id)
        self._update_bulk_bar()

    def _update_bulk_bar(self) -> None:
        self.bulk_bar.set_selection_count(len(self._selected_ids))

    def _clear_selection(self) -> None:
        self.data_table.clear_selection()
        self._selected_ids = []
        self._update_bulk_bar()

    def _bulk_delete(self) -> None:
        if not self._selected_ids:
            return
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(
                "You must be in WRITE mode to delete students.", "warning"
            )
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete {len(self._selected_ids)} students?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                for student_id in self._selected_ids:
                    self._student_service.delete_student(student_id)
                self._clear_selection()
                self.refresh()
            except Exception:
                logger.exception("Bulk delete failed")
                QMessageBox.critical(self, "Error", "Failed to delete students.")

    def _bulk_export(self) -> None:
        if not self._selected_ids:
            return
        try:
            students = [
                self._student_service.get_student(student_id)
                for student_id in self._selected_ids
            ]
            file_path = self._export_service.export_csv(students)
            QMessageBox.information(
                self,
                "Export",
                f"Exported {len(students)} students to {file_path}",
            )
        except Exception:
            logger.exception("Bulk export failed")
            QMessageBox.critical(self, "Error", "Failed to export students.")

    def _on_row_double_clicked(self, row: int) -> None:
        data_index = self.data_table.data_index_for_visible_row(row)
        if 0 <= data_index < len(self._filtered):
            self.student_selected.emit(self._filtered[data_index].id)

    def _on_context_menu(self, pos, row: int) -> None:
        data_index = self.data_table.data_index_for_visible_row(row)
        if data_index < 0 or data_index >= len(self._filtered):
            return
        student = self._filtered[data_index]
        menu = QMenu(self)
        view_action = QAction("View Student", self)
        view_action.triggered.connect(lambda: self.student_selected.emit(student.id))
        menu.addAction(view_action)

        can_write = self.can_write()
        edit_action = QAction("Edit Student", self)
        edit_action.setEnabled(can_write)
        edit_action.triggered.connect(lambda: self._edit_student(student.id))
        menu.addAction(edit_action)

        menu.addSeparator()

        if student.status == "ARCHIVED":
            activate_action = QAction("Activate Student", self)
            activate_action.setEnabled(can_write)
            activate_action.triggered.connect(lambda: self._activate_student(student.id))
            menu.addAction(activate_action)
        else:
            archive_action = QAction("Archive Student", self)
            archive_action.setEnabled(can_write)
            archive_action.triggered.connect(lambda: self._archive_student(student.id))
            menu.addAction(archive_action)

        menu.addSeparator()
        delete_action = QAction("Delete Student", self)
        delete_action.setEnabled(can_write)
        delete_action.triggered.connect(lambda: self._delete_student(student.id))
        menu.addAction(delete_action)

        menu.exec(pos)

    def _archive_student(self, student_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(
                "You must be in WRITE mode to archive.", "warning"
            )
            return
        reply = QMessageBox.question(
            self,
            "Confirm Archive",
            "Archive this student? They will not appear in default lists.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._student_service.archive_student(student_id)
                self.refresh()
            except Exception as e:
                logger.exception("Archive failed")
                QMessageBox.critical(self, "Error", str(e))

    def _activate_student(self, student_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(
                "You must be in WRITE mode to activate.", "warning"
            )
            return
        try:
            self._student_service.activate_student(student_id)
            self.refresh()
        except Exception as e:
            logger.exception("Activate failed")
            QMessageBox.critical(self, "Error", str(e))

    def _edit_student(self, student_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(
                "You must be in WRITE mode to edit.", "warning"
            )
            return
        dialog = StudentFormDialog(
            self._student_service,
            student_id=student_id,
            parent=self,
        )
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self.refresh()

    def _delete_student(self, student_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(
                "You must be in WRITE mode to delete.", "warning"
            )
            return
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            "Delete this student?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._student_service.delete_student(student_id)
                self.refresh()
            except Exception:
                logger.exception("Delete failed")
                QMessageBox.critical(self, "Error", "Failed to delete student.")

    def show_add_dialog(self) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(
                "You must be in WRITE mode to add a student.", "warning"
            )
            return
        dialog = StudentFormDialog(self._student_service, parent=self)
        if dialog.exec() == StudentFormDialog.DialogCode.Accepted:
            self.refresh()

    def show_import_dialog(self) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(
                "You must be in WRITE mode to import.", "warning"
            )
            return
        dialog = StudentImportDialog(self._import_service, parent=self)
        if dialog.exec() == StudentImportDialog.DialogCode.Accepted:
            self.refresh()

    def export_students(self) -> None:
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
                    self._filtered_base = self._filter_service.filter_students(
                        filter_criteria
                    )
                    self._apply_filters_and_sort()
                except Exception as e:
                    QMessageBox.critical(self, "Filter Error", str(e))

    def set_write_enabled(self, enabled: bool) -> None:
        self.add_btn.setEnabled(enabled)
        self.import_btn.setEnabled(enabled)
        self.bulk_delete_btn.setEnabled(enabled)
        # Export/filter/refresh/search remain read-only operations.
