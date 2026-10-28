# -*- coding: utf-8 -*-
"""
ClassListPage - list of classes with search, filter, CRUD.
Now with collaboration support.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QMessageBox, QMenu
)
from PySide6.QtGui import QAction

from centermanager.models.class_ import Class
from centermanager.services.class_service import ClassService
from centermanager.services.class_timeline_service import ClassTimelineService
from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.ui.design_system.foundation import ButtonVariant, Toolbar
from centermanager.ui.shared import (
    BulkActionBar, DataTable, LoadingWidget, SearchToolbar, TableDensity
)
from centermanager.ui.class_workspace.class_form_dialog import ClassFormDialog
from centermanager.ui.class_workspace.class_detail_page import ClassDetailPage
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService


logger = logging.getLogger(__name__)


class ClassListPage(QWidget):
    class_selected = Signal(int)

    def __init__(
        self,
        class_service: ClassService,
        assignment_service: TeacherAssignmentService,
        timeline_service: ClassTimelineService,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._class_service = class_service
        self._assignment_service = assignment_service
        self._timeline_service = timeline_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._classes: List[Class] = []
        self._filtered: List[Class] = []
        self._sort_key: Optional[str] = "name"
        self._sort_asc: bool = True
        self._selected_ids: List[int] = []

        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        toolbar = Toolbar(self)
        self.search_bar = SearchToolbar(
            placeholder="Search by name, course, teacher...",
            filters=[
                {"key": "status", "label": "Status", "options": ["Active", "Inactive", "Archived"]},
            ],
            parent=toolbar,
        )
        self.search_bar.search_changed.connect(self._on_search)
        self.search_bar.filters_changed.connect(self._on_status_filters_changed)
        status_control = self.search_bar.filter_controls["status"]
        self.status_filter = status_control  # compatibility alias
        previous = status_control.blockSignals(True)
        self.search_bar.set_filter_value("status", "Active")
        status_control.blockSignals(previous)
        toolbar.add_widget(self.search_bar, align="start")

        self.refresh_btn = toolbar.add_action(
            "Refresh", self.refresh, variant=ButtonVariant.SECONDARY
        )
        self.add_btn = toolbar.add_action(
            "Add Class", self.show_add_dialog, variant=ButtonVariant.PRIMARY
        )

        self.bulk_bar = BulkActionBar(toolbar)
        self.bulk_archive_btn = self.bulk_bar.add_action(
            "archive",
            "Archive selected",
            self._bulk_archive,
            variant=ButtonVariant.DANGER,
        )
        self.bulk_bar.clear_requested.connect(self._clear_selection)
        self.bulk_count_label = self.bulk_bar.count_label
        self.bulk_clear_btn = self.bulk_bar.clear_button
        toolbar.add_widget(self.bulk_bar, align="end")
        layout.addWidget(toolbar)

        # Data Table
        columns = [
            {"key": "name", "label": "Class", "sortable": True},
            {"key": "course", "label": "Course", "sortable": True},
            {"key": "teacher_names", "label": "Teacher", "sortable": False},
            {"key": "student_count", "label": "Students", "sortable": False},
            {"key": "status", "label": "Status", "sortable": True},
            {"key": "schedule", "label": "Schedule", "sortable": False},
        ]
        self.data_table = DataTable(
            columns,
            page_size=20,
            density=TableDensity.COMPACT,
            empty_title="No classes found",
            empty_message="Class records matching the current view will appear here.",
        )
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
            self._classes = self._class_service.list_classes(include_archived=True)
            self._apply_filters_and_sort()
        except Exception as e:
            logger.exception("Failed to refresh class list")
            QMessageBox.critical(self, "Error", "Failed to load classes.")
        finally:
            self.loading.setVisible(False)

    def _apply_filters_and_sort(self) -> None:
        filtered = self._filter_classes(self.search_bar.text())
        if self._sort_key:
            filtered.sort(
                key=lambda c: (getattr(c, self._sort_key, "") or "").casefold()
                if isinstance(getattr(c, self._sort_key, ""), str)
                else getattr(c, self._sort_key, ""),
                reverse=not self._sort_asc,
            )
        self._filtered = filtered
        self._populate_table()

    def _filter_classes(self, text: str) -> List[Class]:
        status_map = {"Active": "ACTIVE", "Inactive": "INACTIVE"}
        status_label = self.search_bar.filters().get("status", "")
        status = status_map.get(status_label, "ALL")
        normalized = text.strip().casefold()

        if status_label == "Archived":
            filtered = [
                class_obj for class_obj in self._classes
                if class_obj.deleted_at is not None
            ]
        else:
            filtered = [
                class_obj
                for class_obj in self._classes
                if (
                    (status == "ALL" or (class_obj.status or "ACTIVE") == status)
                    and (status == "ALL" or class_obj.deleted_at is None)
                )
            ]
        if not normalized:
            return filtered

        result = []
        for class_obj in filtered:
            teacher_names = " ".join(
                teacher.full_name
                for teacher in (class_obj.teachers or [])
                if getattr(teacher, "full_name", None)
            )
            haystacks = (
                class_obj.name or "",
                class_obj.course or "",
                teacher_names,
            )
            if any(normalized in value.casefold() for value in haystacks):
                result.append(class_obj)
        return result

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
                "status": "ARCHIVED" if c.deleted_at is not None else (c.status or "ACTIVE"),
                "schedule": schedule,
                "_id": c.id,
            })
        self.data_table.set_data(data, len(data))

    def _on_search(self, text: str) -> None:
        self._apply_filters_and_sort()

    def _on_status_filters_changed(self, _filters) -> None:
        self._clear_selection()
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
        self.bulk_bar.set_selection_count(count)

    def _clear_selection(self) -> None:
        self.data_table.clear_selection()
        self._selected_ids = []
        self._update_bulk_bar()

    def _bulk_archive(self) -> None:
        if not self._selected_ids:
            return
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to archive classes.", "warning")
            return
        try:
            summaries = [
                self._class_service.preview_archive_class(cid)
                for cid in self._selected_ids
            ]
        except Exception:
            logger.exception("Bulk archive impact preview failed")
            QMessageBox.critical(self, "Error", "Could not verify all class dependencies. Archive cancelled.")
            return
        active_count = sum(item["active_enrollments"] for item in summaries)
        session_count = sum(item["sessions"] for item in summaries)
        from decimal import Decimal
        debt_before = sum(Decimal(item["outstanding_before"]) for item in summaries)
        debt_after = sum(Decimal(item["outstanding_after"]) for item in summaries)
        owed_before = sum(Decimal(item["owed_before"]) for item in summaries)
        owed_after = sum(Decimal(item["owed_after"]) for item in summaries)
        credit_before = sum(Decimal(item["credit_before"]) for item in summaries)
        credit_after = sum(Decimal(item["credit_after"]) for item in summaries)
        reply = QMessageBox.question(
            self, "Confirm Archive",
            f"Archive {len(self._selected_ids)} classes?\\n\\n"
            f"Active enrollments affected: {active_count}\\n"
            f"Class sessions preserved as read-only: {session_count}\\n"
            f"Receivables before/after: {owed_before} / {owed_after} VND\\n"
            f"Prepaid credit before/after: {credit_before} / {credit_after} VND\\n"
            f"Net balance before/after: {debt_before} / {debt_after} VND\\n"
            f"Difference: {debt_after - debt_before} VND\\n\\n"
            "Active enrollments will be withdrawn; outstanding tuition remains collectible. "
            "Restore each class before changing its enrollments.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                for cid, impact in zip(self._selected_ids, summaries):
                    self._class_service.archive_class(
                        cid, expected_finance_impact={
                            key: impact[key]
                            for key in (
                                "outstanding_before", "outstanding_after",
                                "outstanding_change", "owed_before", "owed_after",
                                "credit_before", "credit_after", "enrollment_finance_changes",
                            )
                        },
                    )
                self._clear_selection()
                self.refresh()
            except Exception as e:
                logger.exception("Bulk archive failed")
                QMessageBox.critical(self, "Error", "Failed to archive classes.")

    def _on_row_double_clicked(self, row: int) -> None:
        if row >= len(self._filtered):
            return
        class_obj = self._filtered[row]
        if class_obj.deleted_at is not None:
            self._notification_service.notify(
                "Archived class is read-only. Restore it before opening the class workspace.",
                "info",
            )
            return
        self.class_selected.emit(class_obj.id)

    def _on_context_menu(self, pos, row: int) -> None:
        if row < 0 or row >= len(self._filtered):
            return
        class_obj = self._filtered[row]
        menu = QMenu(self)
        view_action = QAction("View Class", self)
        view_action.triggered.connect(lambda: self.class_selected.emit(class_obj.id))
        menu.addAction(view_action)

        if class_obj.deleted_at is None:
            edit_action = QAction("Edit Class", self)
            edit_action.triggered.connect(lambda: self._edit_class(class_obj.id))
            menu.addAction(edit_action)

        menu.addSeparator()
        if class_obj.deleted_at is not None:
            restore_action = QAction("Restore Class", self)
            restore_action.triggered.connect(lambda: self._restore_class(class_obj.id))
            menu.addAction(restore_action)
        else:
            archive_action = QAction("Archive Class", self)
            archive_action.triggered.connect(lambda: self._archive_class(class_obj.id))
            menu.addAction(archive_action)

        menu.exec(pos)

    def _edit_class(self, class_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to edit.", "warning")
            return
        dialog = ClassFormDialog(self._class_service, class_id=class_id, parent=self)
        if dialog.exec() == ClassFormDialog.DialogCode.Accepted:
            self.refresh()

    def _archive_class(self, class_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to archive.", "warning")
            return
        try:
            impact = self._class_service.preview_archive_class(class_id)
        except Exception:
            logger.exception("Archive impact preview failed")
            QMessageBox.critical(self, "Error", "Could not verify class dependencies. Archive cancelled.")
            return
        finance_changes = impact["enrollment_finance_changes"]
        changed_rows = [
            row for row in finance_changes if row["before"] != row["after"]
        ]
        finance_message = (
            f"Receivables before/after: {impact['owed_before']} / {impact['owed_after']} VND\\n"
            f"Prepaid credit before/after: {impact['credit_before']} / {impact['credit_after']} VND\\n"
            f"Net balance before/after: {impact['outstanding_before']} / {impact['outstanding_after']} VND\\n"
            f"Difference: {impact['outstanding_change']} VND\\n"
            f"Changed student balances: {len(changed_rows)}\\n\\n"
            "These figures are calculated from the existing tuition rules. "
            "Please verify the impact before confirming.\\n\\n"
        )
        reply = QMessageBox.question(
            self, "Confirm Archive",
            finance_message +
            "Archiving this class will make its enrollment and class records "
            "read-only until restored. Active enrollments WILL be withdrawn "
            "automatically. Outstanding tuition remains collectible.\\n\\n"
            f"Active enrollments: {impact['active_enrollments']}\\n"
            f"Teacher assignments: {impact['teacher_assignments']}\\n"
            f"Class sessions: {impact['sessions']}\\n\\n"
            "Archive this class anyway?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._class_service.archive_class(
                    class_id, expected_finance_impact={
                        key: impact[key]
                        for key in (
                            'outstanding_before', 'outstanding_after',
                            'outstanding_change', 'owed_before', 'owed_after',
                            'credit_before', 'credit_after', 'enrollment_finance_changes',
                        )
                    },
                )
                self.refresh()
            except Exception as e:
                logger.exception("Archive failed")
                QMessageBox.critical(self, "Error", "Failed to archive class.")

    def _restore_class(self, class_id: int) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(
                "You must be in WRITE mode to restore a class.", "warning"
            )
            return
        reply = QMessageBox.question(
            self,
            "Confirm Restore",
            "Restore this archived class?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._class_service.restore_class(class_id)
                self.refresh()
            except Exception:
                logger.exception("Restore failed")
                QMessageBox.critical(self, "Error", "Failed to restore class.")

    def show_add_dialog(self) -> None:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify("You must be in WRITE mode to add a class.", "warning")
            return
        dialog = ClassFormDialog(self._class_service, parent=self)
        if dialog.exec() == ClassFormDialog.DialogCode.Accepted:
            self.refresh()

    def set_write_enabled(self, enabled: bool) -> None:
        self.add_btn.setEnabled(enabled)
        self.bulk_archive_btn.setEnabled(enabled)