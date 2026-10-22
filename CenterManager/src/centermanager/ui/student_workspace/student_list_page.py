# -*- coding: utf-8 -*-
"""StudentListPage - production Student workspace list surface.

UI-PROD-08 keeps Student domain/service behavior intact while moving the page to
Design System V2 feedback, state, table, confirmation, and edit-state patterns.
"""
from __future__ import annotations

import logging
from typing import Dict, List, Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QMenu, QStackedWidget, QVBoxLayout, QWidget

from centermanager.models.student import Student
from centermanager.core.capabilities import Capability
from centermanager.core.current_user import get_current_user
from centermanager.services.authorization_service import AuthorizationService
from centermanager.services.assessment_service import AssessmentService
from centermanager.services.parent_service import ParentService
from centermanager.services.student_export_service import StudentExportService
from centermanager.services.student_filter_service import StudentFilterService
from centermanager.services.student_import_service import StudentImportService
from centermanager.services.student_service import StudentService
from centermanager.ui.design_system.feedback import ConfirmationDialog, FeedbackController
from centermanager.ui.design_system.form_detail import EditStateBanner
from centermanager.ui.design_system.foundation import ButtonVariant, Toolbar
from centermanager.ui.design_system.state_patterns import EmptySearchState
from centermanager.ui.design_system.tokens import SPACING
from centermanager.ui.shared import BulkActionBar, DataTable, SearchToolbar, TableDensity
from centermanager.ui.students.student_filter_dialog import StudentFilterDialog
from centermanager.ui.students.student_form_dialog import StudentFormDialog
from centermanager.ui.students.student_import_dialog import StudentImportDialog

from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.context import PlatformContext
from centermanager.ui.workspace_base import WorkspaceBase

logger = logging.getLogger(__name__)


class StudentListPage(WorkspaceBase):
    """Data-heavy Student list using the shared production interaction contract."""

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
        feedback_controller: Optional[FeedbackController] = None,
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

        self._feedback = feedback_controller or FeedbackController(self)
        self._students: List[Student] = []
        self._filtered: List[Student] = []
        self._filtered_base: List[Student] = []
        self._sort_key: Optional[str] = "student_code"
        self._sort_asc = True
        self._current_page = 1
        self._page_size = 20
        self._total_rows = 0
        self._advanced_filter_active = False
        self._advanced_filter_criteria = None
        self._selected_ids: List[int] = []
        self._filters_active = False
        self._write_enabled = False

        self._setup_ui()
        self.refresh()
        self._is_initialized = True

    def set_feedback_controller(self, controller: FeedbackController) -> None:
        """Rebind transient feedback to the application-level UI-PROD-07 host."""
        self._feedback = controller

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.edit_state_banner = EditStateBanner("readonly", parent=self)
        layout.addWidget(self.edit_state_banner)

        toolbar = Toolbar(self)
        self.search_bar = SearchToolbar(
            placeholder="Search by code, name, parent phone, parent name...",
            filters=[
                {"key": "status", "label": "Status", "options": ["Active", "Archived", "Deleted"]},
                {"key": "enrollment", "label": "Enrollment", "options": ["Enrolled", "Not Enrolled"]},
                {"key": "assessment", "label": "Assessment", "options": ["Has Assessment", "No Assessment"]},
            ],
            parent=toolbar,
        )
        self.search_bar.search_changed.connect(self._on_search_text_changed)
        self.search_bar.filters_changed.connect(self._on_filter_changed)
        # Product default: the operational Student list opens on ACTIVE records.
        # "All" remains available through the filter placeholder/clear action.
        status_control = self.search_bar.filter_controls.get("status")
        if status_control is not None:
            status_control.blockSignals(True)
            self.search_bar.set_filter_value("status", "Active")
            status_control.blockSignals(False)
        self.filter_bar = self.search_bar
        toolbar.add_widget(self.search_bar, align="start")

        self.filter_btn = toolbar.add_action("More filters", self.filter_clicked.emit, variant=ButtonVariant.SECONDARY)
        # Student clear is intentionally atomic: reset the whole toolbar and
        # execute exactly one server refresh instead of one refresh per control.
        self.search_bar.clear_btn.clicked.disconnect(self.search_bar.clear)
        self.search_bar.clear_btn.clicked.connect(self._clear_toolbar_filters)
        self.refresh_btn = toolbar.add_action("Refresh", self.refresh, variant=ButtonVariant.SECONDARY)
        self.import_btn = toolbar.add_action("Import", self.show_import_dialog, variant=ButtonVariant.SECONDARY)
        self.export_btn = toolbar.add_action("Export", self.export_students, variant=ButtonVariant.SECONDARY)
        self.add_btn = toolbar.add_action("Add student", self.show_add_dialog, variant=ButtonVariant.PRIMARY)

        # Keep selection feedback/actions inside the existing toolbar. Toggling
        # selection must not insert/remove a vertical row and move the table.
        self.bulk_bar = BulkActionBar(toolbar)
        self.bulk_delete_btn = self.bulk_bar.add_action(
            "delete", "Delete selected", self._bulk_delete, variant=ButtonVariant.DANGER
        )
        self.bulk_export_btn = self.bulk_bar.add_action(
            "export", "Export selected", self._bulk_export, variant=ButtonVariant.SECONDARY
        )
        self.bulk_bar.clear_requested.connect(self._clear_selection)
        self.bulk_count_label = self.bulk_bar.count_label
        self.bulk_clear_btn = self.bulk_bar.clear_button
        toolbar.add_widget(self.bulk_bar, align="end")
        layout.addWidget(toolbar)

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
            empty_title="No students yet",
            empty_message="Student records will appear here after they are created or imported.",
        )
        self.data_table.sort_requested.connect(self._on_sort)
        self.data_table.page_requested.connect(self._on_page_requested)
        self.data_table.selection_changed.connect(self._on_selection_changed)
        self.data_table.row_double_clicked.connect(self._on_row_double_clicked)
        self.data_table.context_menu_requested.connect(self._on_context_menu)

        self.empty_search_state = EmptySearchState(
            clear_callback=self._clear_toolbar_filters,
            parent=self,
        )
        self.list_state_stack = QStackedWidget(self)
        self.list_state_stack.addWidget(self.data_table)
        self.list_state_stack.addWidget(self.empty_search_state)
        self.list_state_stack.setCurrentWidget(self.data_table)
        layout.addWidget(self.list_state_stack, 1)

        self.loading = self.data_table.loading_state

        self._search_debounce = QTimer(self)
        self._search_debounce.setSingleShot(True)
        self._search_debounce.setInterval(300)
        self._search_debounce.timeout.connect(self._apply_debounced_search)

        self._update_button_states()

    def _update_button_states(self) -> None:
        can_write = bool(self._write_enabled or self.can_write())
        can_export = AuthorizationService.allows(
            get_current_user(),
            Capability.STUDENT_EXPORT,
        )
        self.add_btn.setEnabled(can_write)
        self.import_btn.setEnabled(can_write)
        self.bulk_delete_btn.setEnabled(can_write)
        self.export_btn.setEnabled(can_export)
        self.bulk_export_btn.setEnabled(can_export)
        self.export_btn.setToolTip(
            "Export student records"
            if can_export
            else "You do not have permission to export student records."
        )

    def initialize(self) -> None:
        pass

    def _toolbar_filter_values(self):
        from centermanager.dto.student_filter_dto import StudentFilter

        filters = self.search_bar.filters()
        status_map = {"Active": "ACTIVE", "Archived": "ARCHIVED", "Deleted": "DELETED"}
        enrollment_map = {"Enrolled": "enrolled", "Not Enrolled": "not_enrolled"}
        assessment_map = {"Has Assessment": "has_assessment", "No Assessment": "no_assessment"}
        return StudentFilter(
            status=status_map.get(filters.get("status", "")),
            enrollment_status=enrollment_map.get(filters.get("enrollment", "")),
            assessment_status=assessment_map.get(filters.get("assessment", "")),
        )

    def refresh(self) -> None:
        """Refresh the current view without discarding the user's list context."""
        if self._advanced_filter_active and self._advanced_filter_criteria is not None:
            try:
                self._filtered_base = self._filter_service.filter_students(
                    self._advanced_filter_criteria
                )
                self._apply_filters_and_sort()
            except Exception as exc:
                logger.exception("Advanced filter refresh failed")
                self._feedback.system_error(
                    exc,
                    message="The student filters could not be refreshed.",
                    key="student-filter",
                )
            return
        self._load_server_page()

    def _load_server_page(self) -> None:
        self.list_state_stack.setCurrentWidget(self.data_table)
        self.data_table.set_loading(True)
        self._selected_ids = []
        self._update_bulk_bar()
        try:
            criteria = self._toolbar_filter_values()
            self._filters_active = any(value for value in self.search_bar.filters().values())
            items, total = self._student_service.search_students_page(
                search_text=self.search_bar.text().strip(),
                status=criteria.status,
                enrollment_status=criteria.enrollment_status,
                assessment_status=criteria.assessment_status,
                page=self._current_page,
                per_page=self._page_size,
                sort_by=self._sort_key or "student_code",
                ascending=self._sort_asc,
            )
            max_page = max(1, (total + self._page_size - 1) // self._page_size)
            if self._current_page > max_page:
                self._current_page = max_page
                items, total = self._student_service.search_students_page(
                    search_text=self.search_bar.text().strip(),
                    status=criteria.status,
                    enrollment_status=criteria.enrollment_status,
                    assessment_status=criteria.assessment_status,
                    page=self._current_page,
                    per_page=self._page_size,
                    sort_by=self._sort_key or "student_code",
                    ascending=self._sort_asc,
                )
            self._filtered = list(items)
            self._total_rows = total
            self._populate_table(server_side=True)
        except Exception as exc:
            logger.exception("Failed to refresh student list")
            self.data_table.set_error(
                "Student records could not be loaded.",
                title="Unable to load students",
                retry_callback=self.refresh,
            )
            self._feedback.system_error(
                exc,
                message="Student records could not be loaded. Try again.",
                retry_action_id="student-list-refresh",
                key="student-list-load",
            )
        self.data_updated.emit()
        self._update_button_states()

    def _apply_filters_and_sort(self) -> None:
        """Legacy advanced-filter fallback; parents are batch-loaded by repository."""
        filtered = self._filter_students(self.search_bar.text())
        if self._sort_key:
            filtered.sort(
                key=lambda student: getattr(student, self._sort_key, "") or "",
                reverse=not self._sort_asc,
            )
        self._filtered = filtered
        self._populate_table(server_side=False)

    def _filter_students(self, text: str) -> List[Student]:
        base = self._filtered_base
        if not text.strip():
            return base[:]

        lower = text.strip().lower()
        results: List[Student] = []
        for student in base:
            student_code = (student.student_code or "").lower()
            full_name = (student.full_name or "").lower()
            preferred_name = (student.preferred_name or "").lower()
            if (
                lower in student_code
                or lower in full_name
                or lower in preferred_name
            ):
                results.append(student)
                continue
            for parent in getattr(student, "parents", None) or []:
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

    def _populate_table(self, *, server_side: bool) -> None:
        data = [
            {
                "student_code": student.student_code,
                "full_name": student.full_name,
                "status": student.status or "",
                "current_level": student.current_level or "",
                "created_at": student.created_at.strftime("%d/%m/%Y") if student.created_at else "",
                "_id": student.id,
            }
            for student in self._filtered
        ]
        if server_side:
            self.data_table.set_server_data(
                data,
                self._total_rows,
                page=self._current_page,
                page_size=self._page_size,
            )
        else:
            self.data_table.set_data(data, len(data))

        has_search_context = bool(self.search_bar.text().strip() or self._filters_active)
        if not data and has_search_context:
            query = self.search_bar.text().strip()
            self.empty_search_state.title_label.setText("No results found")
            self.empty_search_state.message_label.setText(
                f'No results match "{query}". Try another keyword or clear the filters.'
                if query
                else "No results match the current search or filters."
            )
            self.empty_search_state.message_label.show()
            self.list_state_stack.setCurrentWidget(self.empty_search_state)
        else:
            self.list_state_stack.setCurrentWidget(self.data_table)
        self.data_updated.emit()

    def _on_search_text_changed(self, _text: str) -> None:
        self._search_debounce.start()

    def _apply_debounced_search(self) -> None:
        if self._advanced_filter_active:
            self._apply_filters_and_sort()
            return
        self._current_page = 1
        self._load_server_page()

    def _clear_toolbar_filters(self) -> None:
        """Reset search + toolbar filters atomically and reload once."""
        self._search_debounce.stop()
        widgets = [self.search_bar.search_input, *self.search_bar.filter_controls.values()]
        previous = [widget.blockSignals(True) for widget in widgets]
        try:
            self.search_bar.search_input.clear()
            for combo in self.search_bar.filter_controls.values():
                combo.setCurrentIndex(0)
        finally:
            for widget, blocked in zip(widgets, previous):
                widget.blockSignals(blocked)

        self._advanced_filter_active = False
        self._advanced_filter_criteria = None
        self._filters_active = False
        self.filter_btn.setText("More filters")
        self._current_page = 1
        self._load_server_page()

    def _on_filter_changed(self, _filters: Dict[str, str]) -> None:
        self._search_debounce.stop()
        self._advanced_filter_active = False
        self._advanced_filter_criteria = None
        self.filter_btn.setText("More filters")
        self._current_page = 1
        self._load_server_page()

    def _on_sort(self, key: str, ascending: bool) -> None:
        self._sort_key = key
        self._sort_asc = ascending
        if self._advanced_filter_active:
            self._apply_filters_and_sort()
            return
        self._current_page = 1
        self._load_server_page()

    def _on_page_requested(self, page: int, page_size: int) -> None:
        if self._advanced_filter_active:
            return
        self._current_page = page
        self._page_size = page_size
        self._load_server_page()

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

    def _require_write_action(self, action: str) -> bool:
        if self._collaboration_manager.ensure_write():
            return True
        self._feedback.warning(
            f"Start editing before you {action} students.",
            title="Read-only mode",
            key="student-write-required",
        )
        return False

    def _confirm(self, title: str, message: str, confirm_text: str, *, dangerous: bool) -> bool:
        dialog = ConfirmationDialog(
            title,
            message,
            confirm_text=confirm_text,
            dangerous=dangerous,
            parent=self,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted

    def _bulk_delete(self) -> None:
        if not self._selected_ids or not self._require_write_action("delete"):
            return
        count = len(self._selected_ids)
        if not self._confirm(
            "Delete students",
            f"Delete {count} selected students? This action affects their Student records.",
            "Delete students",
            dangerous=True,
        ):
            return
        operation_id = "student-bulk-delete"
        if not self._feedback.begin_operation(operation_id, "Deleting students…"):
            return
        try:
            for student_id in list(self._selected_ids):
                self._student_service.delete_student(student_id)
            self._clear_selection()
            self.refresh()
            self._feedback.finish_operation(operation_id)
            self._feedback.deleted(message=f"Deleted {count} students", key="student-delete")
        except Exception as exc:
            self._feedback.finish_operation(operation_id)
            logger.exception("Bulk delete failed")
            self._feedback.system_error(
                exc,
                message="The selected students could not be deleted.",
                key="student-delete",
            )

    def _bulk_export(self) -> None:
        if not self._selected_ids:
            return
        operation_id = "student-bulk-export"
        if not self._feedback.begin_operation(operation_id, "Exporting students…"):
            return
        try:
            students = [self._student_service.get_student(student_id) for student_id in self._selected_ids]
            file_path = self._export_service.export_csv(students)
            self._feedback.finish_operation(operation_id)
            self._feedback.success(
                f"Exported {len(students)} students to {file_path}",
                key="student-export",
            )
        except Exception as exc:
            self._feedback.finish_operation(operation_id)
            logger.exception("Bulk export failed")
            self._feedback.system_error(exc, message="The selected students could not be exported.", key="student-export")

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
        view_action = QAction("View student", self)
        view_action.triggered.connect(lambda: self.student_selected.emit(student.id))
        menu.addAction(view_action)

        can_write = self._write_enabled or self.can_write()
        edit_action = QAction("Edit student", self)
        edit_action.setEnabled(can_write)
        edit_action.triggered.connect(lambda: self._edit_student(student.id))
        menu.addAction(edit_action)
        menu.addSeparator()

        if student.status == "ARCHIVED":
            activate_action = QAction("Activate student", self)
            activate_action.setEnabled(can_write)
            activate_action.triggered.connect(lambda: self._activate_student(student.id))
            menu.addAction(activate_action)
        else:
            archive_action = QAction("Archive student", self)
            archive_action.setEnabled(can_write)
            archive_action.triggered.connect(lambda: self._archive_student(student.id))
            menu.addAction(archive_action)

        menu.addSeparator()
        delete_action = QAction("Delete student", self)
        delete_action.setEnabled(can_write)
        delete_action.triggered.connect(lambda: self._delete_student(student.id))
        menu.addAction(delete_action)
        menu.exec(pos)

    def _archive_student(self, student_id: int) -> None:
        if not self._require_write_action("archive"):
            return
        if not self._confirm(
            "Archive student",
            "Archive this student? They will no longer appear in the default active list.",
            "Archive",
            dangerous=False,
        ):
            return
        try:
            self._student_service.archive_student(student_id)
            self.refresh()
            self._feedback.success("Student archived", key="student-lifecycle")
        except Exception as exc:
            logger.exception("Archive failed")
            self._feedback.system_error(exc, message="The student could not be archived.", key="student-lifecycle")

    def _activate_student(self, student_id: int) -> None:
        if not self._require_write_action("activate"):
            return
        try:
            self._student_service.activate_student(student_id)
            self.refresh()
            self._feedback.success("Student activated", key="student-lifecycle")
        except Exception as exc:
            logger.exception("Activate failed")
            self._feedback.system_error(exc, message="The student could not be activated.", key="student-lifecycle")

    def _edit_student(self, student_id: int) -> None:
        if not self._require_write_action("edit"):
            return
        dialog = StudentFormDialog(
            self._student_service,
            student_id=student_id,
            parent=self,
            feedback_controller=self._feedback,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def _delete_student(self, student_id: int) -> None:
        if not self._require_write_action("delete"):
            return
        if not self._confirm(
            "Delete student",
            "Delete this student record?",
            "Delete student",
            dangerous=True,
        ):
            return
        operation_id = f"student-delete-{student_id}"
        if not self._feedback.begin_operation(operation_id, "Deleting student…"):
            return
        try:
            self._student_service.delete_student(student_id)
            self.refresh()
            self._feedback.finish_operation(operation_id)
            self._feedback.deleted(message="Student deleted", key="student-delete")
        except Exception as exc:
            self._feedback.finish_operation(operation_id)
            logger.exception("Delete failed")
            self._feedback.system_error(exc, message="The student could not be deleted.", key="student-delete")

    def show_add_dialog(self) -> None:
        if not self._require_write_action("add"):
            return
        dialog = StudentFormDialog(
            self._student_service,
            parent=self,
            feedback_controller=self._feedback,
        )
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()

    def show_import_dialog(self) -> None:
        if not self._require_write_action("import"):
            return
        dialog = StudentImportDialog(self._import_service, parent=self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.refresh()
            self._feedback.success("Student import completed", key="student-import")

    def export_students(self) -> None:
        operation_id = "student-export-all"
        if not self._feedback.begin_operation(operation_id, "Exporting students…"):
            return
        try:
            file_path = self._export_service.export_all_active()
            self._feedback.finish_operation(operation_id)
            self._feedback.success(f"Students exported to {file_path}", key="student-export")
        except Exception as exc:
            self._feedback.finish_operation(operation_id)
            logger.exception("Export failed")
            self._feedback.system_error(exc, message="Students could not be exported.", key="student-export")

    def show_filter_dialog(self) -> None:
        dialog = StudentFilterDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        filter_criteria = dialog.get_filter()
        if not filter_criteria:
            return
        try:
            self._filters_active = True
            self._advanced_filter_active = True
            self._advanced_filter_criteria = filter_criteria
            self.filter_btn.setText("More filters • Active")
            self._filtered_base = self._filter_service.filter_students(filter_criteria)
            self._apply_filters_and_sort()
        except Exception as exc:
            logger.exception("Advanced filter failed")
            self._feedback.system_error(exc, message="The student filters could not be applied.", key="student-filter")

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self.edit_state_banner.set_state("editing" if enabled else "readonly")
        self.add_btn.setEnabled(enabled)
        self.import_btn.setEnabled(enabled)
        self.bulk_delete_btn.setEnabled(enabled)
        # Export/filter/refresh/search remain available in read-only mode.
