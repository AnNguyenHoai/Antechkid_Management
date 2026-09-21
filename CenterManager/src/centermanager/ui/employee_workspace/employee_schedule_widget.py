from __future__ import annotations

import logging
from datetime import date, timedelta

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QDialogButtonBox, QComboBox, QDateEdit, QTimeEdit,
    QFormLayout, QLineEdit, QMessageBox, QGroupBox, QCheckBox, QHeaderView,
    QLabel, QInputDialog,
)
from centermanager.models.employee_schedule import (
    VALID_EXCEPTION_TYPES,
    EmployeeScheduleAssignment,
    EmployeeScheduleWeek,
)
from centermanager.ui.employee_workspace.error_boundary import execute_ui_operation

logger = logging.getLogger(__name__)
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class ScheduleRuleDialog(QDialog):
    def __init__(self, parent=None, rule=None):
        super().__init__(parent)
        self.rule = rule
        self.setWindowTitle("Schedule Template Rule")
        self.setMinimumWidth(420)
        f = QFormLayout(self)
        self.day = QComboBox(); self.day.addItems(DAYS)
        self.start = QTimeEdit(); self.start.setDisplayFormat("HH:mm"); self.start.setTime(QTime(9, 0))
        self.end = QTimeEdit(); self.end.setDisplayFormat("HH:mm"); self.end.setTime(QTime(17, 0))
        self.frm = QDateEdit(); self.frm.setCalendarPopup(True); self.frm.setDisplayFormat("dd/MM/yyyy"); self.frm.setDate(QDate.currentDate())
        self.to = QDateEdit(); self.to.setCalendarPopup(True); self.to.setDisplayFormat("dd/MM/yyyy"); self.to.setDate(QDate.currentDate())
        self.no_end = QCheckBox("No end date"); self.no_end.setChecked(True)
        self.notes = QLineEdit(); self.notes.setPlaceholderText("Optional")
        for label, widget in (("Day", self.day), ("Start", self.start), ("End", self.end), ("Effective from", self.frm), ("Effective to", self.to), ("", self.no_end), ("Notes", self.notes)):
            f.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); f.addRow(buttons)
        if rule:
            self.day.setCurrentIndex(rule.day_of_week)
            self.start.setTime(QTime(rule.start_time.hour, rule.start_time.minute))
            self.end.setTime(QTime(rule.end_time.hour, rule.end_time.minute))
            self.frm.setDate(QDate(rule.effective_from.year, rule.effective_from.month, rule.effective_from.day))
            self.notes.setText(rule.notes or "")
            if rule.effective_to:
                self.to.setDate(QDate(rule.effective_to.year, rule.effective_to.month, rule.effective_to.day))
                self.no_end.setChecked(False)

    def values(self):
        return (
            self.day.currentIndex(), self.start.time().toPython(), self.end.time().toPython(),
            self.frm.date().toPython(), None if self.no_end.isChecked() else self.to.date().toPython(),
            self.notes.text().strip() or None,
        )


class ScheduleExceptionDialog(QDialog):
    def __init__(self, parent=None, exception=None):
        super().__init__(parent)
        self.setWindowTitle("Schedule Template Exception")
        self.setMinimumWidth(420)
        f = QFormLayout(self)
        self.day = QDateEdit(); self.day.setCalendarPopup(True); self.day.setDisplayFormat("dd/MM/yyyy"); self.day.setDate(QDate.currentDate())
        self.typ = QComboBox(); self.typ.addItems(sorted(VALID_EXCEPTION_TYPES))
        self.start = QTimeEdit(); self.start.setDisplayFormat("HH:mm"); self.start.setTime(QTime(9, 0))
        self.end = QTimeEdit(); self.end.setDisplayFormat("HH:mm"); self.end.setTime(QTime(17, 0))
        self.notes = QLineEdit()
        for label, widget in (("Date", self.day), ("Type", self.typ), ("Start", self.start), ("End", self.end), ("Notes", self.notes)):
            f.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept); buttons.rejected.connect(self.reject); f.addRow(buttons)
        self.typ.currentTextChanged.connect(self._toggle)
        if exception:
            self.day.setDate(QDate(exception.schedule_date.year, exception.schedule_date.month, exception.schedule_date.day))
            self.typ.setCurrentText(exception.exception_type); self.notes.setText(exception.notes or "")
            if exception.start_time: self.start.setTime(QTime(exception.start_time.hour, exception.start_time.minute))
            if exception.end_time: self.end.setTime(QTime(exception.end_time.hour, exception.end_time.minute))
        self._toggle(self.typ.currentText())

    def _toggle(self, value):
        self.start.setEnabled(value == "MODIFIED"); self.end.setEnabled(value == "MODIFIED")

    def values(self):
        return (
            self.day.date().toPython(), self.typ.currentText(), self.start.time().toPython(),
            self.end.time().toPython(), self.notes.text().strip() or None,
        )


class WeeklyAssignmentDialog(QDialog):
    def __init__(self, week_start: date, parent=None):
        super().__init__(parent)
        self.week_start = week_start; self.week_end = week_start + timedelta(days=6)
        self.setWindowTitle("Add Weekly Schedule Assignment"); self.setMinimumWidth(420)
        form = QFormLayout(self)
        self.day = QDateEdit(); self.day.setCalendarPopup(True); self.day.setDisplayFormat("dd/MM/yyyy")
        self.day.setMinimumDate(QDate(week_start.year, week_start.month, week_start.day))
        self.day.setMaximumDate(QDate(self.week_end.year, self.week_end.month, self.week_end.day))
        self.day.setDate(QDate(week_start.year, week_start.month, week_start.day))
        self.start = QTimeEdit(); self.start.setDisplayFormat("HH:mm"); self.start.setTime(QTime(9, 0))
        self.end = QTimeEdit(); self.end.setDisplayFormat("HH:mm"); self.end.setTime(QTime(17, 0))
        self.note = QLineEdit(); self.note.setPlaceholderText("Optional planning note")
        for label, widget in (("Work date", self.day), ("Start", self.start), ("End", self.end), ("Note", self.note)):
            form.addRow(label, widget)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept_if_valid); buttons.rejected.connect(self.reject); form.addRow(buttons)

    def _accept_if_valid(self):
        if self.start.time() >= self.end.time():
            QMessageBox.warning(self, "Weekly Schedule", "End time must be after start time."); return
        self.accept()

    def values(self):
        return self.day.date().toPython(), self.start.time().toPython(), self.end.time().toPython(), self.note.text().strip() or None


class EmployeeScheduleWidget(QWidget):
    """Schedule Template plus publishable Monday-Sunday operational schedule."""

    def __init__(self, service, employee, editable=False, parent=None):
        super().__init__(parent)
        self.service = service; self.employee = employee; self.editable = bool(editable)
        self._week_start = self.service.next_week(); self._week_status = None; self._week_version = None
        self._build(); self.refresh()

    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        weekly_box = QGroupBox("Weekly Plan")
        weekly_layout = QVBoxLayout(weekly_box)
        week_bar = QHBoxLayout()
        self.prev_week = QPushButton("‹ Previous"); self.week_label = QLabel(); self.week_label.setStyleSheet("font-weight:700;"); self.next_week = QPushButton("Next ›")
        week_bar.addWidget(self.prev_week); week_bar.addStretch(); week_bar.addWidget(self.week_label); week_bar.addStretch(); week_bar.addWidget(self.next_week)
        weekly_layout.addLayout(week_bar)
        self.week_summary = QLabel(); self.week_summary.setStyleSheet("color:#55616b;font-weight:600;"); weekly_layout.addWidget(self.week_summary)
        self.lifecycle_summary = QLabel(); self.lifecycle_summary.setStyleSheet("font-weight:700;"); weekly_layout.addWidget(self.lifecycle_summary)

        self.weekly = QTableWidget(0, 4); self.weekly.setHorizontalHeaderLabels(["Date", "Time", "Source", "Note"])
        self.weekly.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.weekly.setSelectionMode(QTableWidget.SelectionMode.SingleSelection); self.weekly.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.weekly.setMinimumHeight(170)
        self.weekly.verticalHeader().setDefaultSectionSize(32)
        for column in range(3): self.weekly.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.weekly.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch); weekly_layout.addWidget(self.weekly)

        wb = QHBoxLayout()
        self.seed_registration = QPushButton("Use Approved Availability"); self.seed_template = QPushButton("Use Template"); self.add_assignment = QPushButton("Add Assignment"); self.delete_assignment = QPushButton("Delete")
        self.publish_week = QPushButton("Publish Entire Week"); self.freeze_week = QPushButton("Freeze Week"); self.override_week = QPushButton("Re-open for Override")
        for button in (self.seed_registration, self.seed_template, self.add_assignment, self.delete_assignment): wb.addWidget(button)
        wb.addStretch()
        for button in (self.publish_week, self.freeze_week, self.override_week): wb.addWidget(button)
        weekly_layout.addLayout(wb); root.addWidget(weekly_box)

        rules_box = QGroupBox("Schedule Template • Recurring Rules"); rl = QVBoxLayout(rules_box)
        self.rules = QTableWidget(0, 5); self.rules.setHorizontalHeaderLabels(["Day", "Time", "Effective from", "Effective to", "Notes"]); self.rules.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.rules.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.rules.setMinimumHeight(190); self.rules.verticalHeader().setDefaultSectionSize(32)
        for column in range(4): self.rules.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.rules.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch); rl.addWidget(self.rules)
        rb = QHBoxLayout(); self.add_rule = QPushButton("Add Rule"); self.edit_rule = QPushButton("Edit"); self.del_rule = QPushButton("Delete")
        for button in (self.add_rule, self.edit_rule, self.del_rule): rb.addWidget(button)
        rb.addStretch(); rl.addLayout(rb); root.addWidget(rules_box)

        ex_box = QGroupBox("Schedule Template • Date Exceptions"); el = QVBoxLayout(ex_box)
        self.exceptions = QTableWidget(0, 4); self.exceptions.setHorizontalHeaderLabels(["Date", "Type", "Time", "Notes"]); self.exceptions.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.exceptions.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.exceptions.setMinimumHeight(150); self.exceptions.verticalHeader().setDefaultSectionSize(32)
        for column in range(3): self.exceptions.horizontalHeader().setSectionResizeMode(column, QHeaderView.ResizeMode.ResizeToContents)
        self.exceptions.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch); el.addWidget(self.exceptions)
        eb = QHBoxLayout(); self.add_ex = QPushButton("Add Exception"); self.del_ex = QPushButton("Delete")
        eb.addWidget(self.add_ex); eb.addWidget(self.del_ex); eb.addStretch(); el.addLayout(eb); root.addWidget(ex_box)

        self.prev_week.clicked.connect(lambda: self._move_week(-7)); self.next_week.clicked.connect(lambda: self._move_week(7))
        self.seed_registration.clicked.connect(self._seed_registration); self.seed_template.clicked.connect(self._seed_template); self.add_assignment.clicked.connect(self._add_assignment); self.delete_assignment.clicked.connect(self._delete_assignment)
        self.publish_week.clicked.connect(self._publish_week); self.freeze_week.clicked.connect(self._freeze_week); self.override_week.clicked.connect(self._override_week)
        self.weekly.itemSelectionChanged.connect(self._update_assignment_actions)
        self.add_rule.clicked.connect(self._add_rule); self.edit_rule.clicked.connect(self._edit_rule); self.del_rule.clicked.connect(self._delete_rule); self.add_ex.clicked.connect(self._add_exception); self.del_ex.clicked.connect(self._delete_exception)
        self.set_editable(self.editable)

    def set_editable(self, enabled):
        self.editable = bool(enabled)
        for button in (self.add_rule, self.edit_rule, self.del_rule, self.add_ex, self.del_ex): button.setEnabled(self.editable)
        self._update_assignment_actions()

    def _update_assignment_actions(self):
        draft = self._week_status in (None, EmployeeScheduleWeek.STATUS_DRAFT)
        can_plan = self.editable and draft
        self.seed_registration.setEnabled(can_plan); self.seed_template.setEnabled(can_plan); self.add_assignment.setEnabled(can_plan)
        self.delete_assignment.setEnabled(can_plan and self.weekly.currentRow() >= 0)
        self.publish_week.setVisible(self.editable); self.freeze_week.setVisible(self.editable); self.override_week.setVisible(self.editable)
        self.publish_week.setEnabled(self.editable and draft and self.weekly.rowCount() > 0)
        self.freeze_week.setEnabled(self.editable and self._week_status == EmployeeScheduleWeek.STATUS_PUBLISHED)
        self.override_week.setEnabled(self.editable and self._week_status in {EmployeeScheduleWeek.STATUS_PUBLISHED, EmployeeScheduleWeek.STATUS_FROZEN})

    def _handle_error(self, title, exc):
        QMessageBox.warning(self, title, f"Operation failed.\n\nReason: {exc}\n\nSee application log for technical details.")

    def _move_week(self, days):
        self._week_start += timedelta(days=days); self.refresh_weekly()

    def refresh_weekly(self):
        week_end = self._week_start + timedelta(days=6)
        self.week_label.setText(f"{self._week_start:%d/%m/%Y} – {week_end:%d/%m/%Y}")

        def action():
            state = self.service.employee_week_state(self.employee.id, self._week_start)
            self._week_status = state["status"]; self._week_version = state["version"]
            if self.editable:
                assignments = self.service.list_employee_week(self.employee.id, self._week_start)
                summary = self.service.registered_vs_scheduled(self.employee.id, self._week_start)
                registration_status = summary["registration_status"] or "NO ACCEPTED REGISTRATION"
                self.week_summary.setText(
                    f"Registration: {registration_status}  •  Registered: {summary['registered_hours']:.2f}h  •  Scheduled: {summary['scheduled_hours']:.2f}h  •  Remaining: {summary['remaining_hours']:.2f}h"
                )
            else:
                assignments = self.service.list_official_employee_week(self.employee.id, self._week_start)
                official_hours = sum(((x.end_time.hour * 60 + x.end_time.minute) - (x.start_time.hour * 60 + x.start_time.minute)) for x in assignments) / 60
                self.week_summary.setText(f"Official scheduled hours: {official_hours:.2f}h")
            status_text = self._week_status or "NOT CREATED"
            version_text = f"v{self._week_version}" if self._week_version is not None else "—"
            if not self.editable and not state["official"]:
                status_text = "NOT PUBLISHED"
            self.lifecycle_summary.setText(f"Schedule: {status_text}  •  Version: {version_text}")
            self.weekly.setRowCount(0)
            for item in assignments:
                row = self.weekly.rowCount(); self.weekly.insertRow(row)
                values = [item.work_date.strftime("%a %d/%m"), f"{item.start_time:%H:%M} – {item.end_time:%H:%M}", item.source, item.note or ""]
                for column, value in enumerate(values): self.weekly.setItem(row, column, QTableWidgetItem(value))
                self.weekly.item(row, 0).setData(Qt.ItemDataRole.UserRole, item.id)
            self.weekly.clearSelection(); self._update_assignment_actions()

        execute_ui_operation(logger_obj=logger, operation="schedule.weekly.refresh", action=action, on_error=lambda exc: self._handle_error("Weekly Schedule", exc), employee_id=self.employee.id, capability="schedule.view")

    def refresh_template(self):
        def action():
            rules = self.service.list_rules(self.employee.id); self.rules.setRowCount(0)
            for rule in rules:
                row = self.rules.rowCount(); self.rules.insertRow(row)
                values = [DAYS[rule.day_of_week], f"{rule.start_time:%H:%M} – {rule.end_time:%H:%M}", rule.effective_from.strftime("%d/%m/%Y"), rule.effective_to.strftime("%d/%m/%Y") if rule.effective_to else "Open-ended", rule.notes or ""]
                for column, value in enumerate(values): self.rules.setItem(row, column, QTableWidgetItem(value))
                self.rules.item(row, 0).setData(Qt.ItemDataRole.UserRole, rule.id)
            exceptions = self.service.list_exceptions(self.employee.id); self.exceptions.setRowCount(0)
            for exception in exceptions:
                row = self.exceptions.rowCount(); self.exceptions.insertRow(row)
                values = [exception.schedule_date.strftime("%d/%m/%Y"), exception.exception_type, f"{exception.start_time:%H:%M} – {exception.end_time:%H:%M}" if exception.start_time and exception.end_time else "—", exception.notes or ""]
                for column, value in enumerate(values): self.exceptions.setItem(row, column, QTableWidgetItem(value))
                self.exceptions.item(row, 0).setData(Qt.ItemDataRole.UserRole, exception.id)

        execute_ui_operation(logger_obj=logger, operation="schedule.template.refresh", action=action, on_error=lambda exc: self._handle_error("Schedule Template", exc), employee_id=self.employee.id, capability="schedule.view")

    def refresh(self):
        self.refresh_weekly(); self.refresh_template()

    def _seed_registration(self):
        if not self.editable: return
        def action():
            created = self.service.seed_week_from_registration(self.employee.id, self._week_start); self.refresh_weekly()
            QMessageBox.information(self, "Weekly Schedule", f"Added {created} assignment(s) from accepted availability.")
        execute_ui_operation(logger_obj=logger, operation="schedule.weekly.seed_registration", action=action, on_error=lambda exc: self._handle_error("Weekly Schedule", exc), employee_id=self.employee.id, capability="schedule.manage")

    def _seed_template(self):
        if not self.editable: return
        def action():
            result = self.service.seed_week_from_template(self.employee.id, self._week_start); self.refresh_weekly()
            QMessageBox.information(self, "Weekly Schedule", f"Added {result['created']} assignment(s) from the template. Skipped {result['skipped_outside_availability']} outside accepted availability.")
        execute_ui_operation(logger_obj=logger, operation="schedule.weekly.seed_template", action=action, on_error=lambda exc: self._handle_error("Weekly Schedule", exc), employee_id=self.employee.id, capability="schedule.manage")

    def _add_assignment(self):
        if not self.editable: return
        dialog = WeeklyAssignmentDialog(self._week_start, self)
        if not dialog.exec(): return
        work_date, start_time, end_time, note = dialog.values()
        execute_ui_operation(logger_obj=logger, operation="schedule.weekly.add_assignment", action=lambda: (self.service.add_week_assignment(self.employee.id, work_date, start_time, end_time, week_start=self._week_start, source=EmployeeScheduleAssignment.SOURCE_MANUAL, note=note), self.refresh_weekly()), on_error=lambda exc: self._handle_error("Weekly Schedule", exc), employee_id=self.employee.id, capability="schedule.manage")

    def _delete_assignment(self):
        row = self.weekly.currentRow()
        if not self.editable or row < 0: return
        assignment_id = self.weekly.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Weekly Schedule", "Delete selected weekly assignment?") != QMessageBox.StandardButton.Yes: return
        execute_ui_operation(logger_obj=logger, operation="schedule.weekly.delete_assignment", action=lambda: (self.service.delete_week_assignment(assignment_id), self.refresh_weekly()), on_error=lambda exc: self._handle_error("Weekly Schedule", exc), employee_id=self.employee.id, record_id=assignment_id, capability="schedule.manage")

    def _publish_week(self):
        if not self.editable or self._week_status not in (None, EmployeeScheduleWeek.STATUS_DRAFT): return
        if QMessageBox.question(self, "Publish Weekly Schedule", "Publish the entire weekly schedule as the official employee schedule? After publishing it is locked until explicitly re-opened.") != QMessageBox.StandardButton.Yes: return
        execute_ui_operation(logger_obj=logger, operation="schedule.weekly.publish", action=lambda: (self.service.publish_week(self._week_start), self.refresh_weekly()), on_error=lambda exc: self._handle_error("Publish Weekly Schedule", exc), employee_id=self.employee.id, capability="schedule.manage")

    def _freeze_week(self):
        if not self.editable or self._week_status != EmployeeScheduleWeek.STATUS_PUBLISHED: return
        if QMessageBox.question(self, "Freeze Weekly Schedule", "Freeze this published week as an immutable operational record?") != QMessageBox.StandardButton.Yes: return
        execute_ui_operation(logger_obj=logger, operation="schedule.weekly.freeze", action=lambda: (self.service.freeze_week(self._week_start), self.refresh_weekly()), on_error=lambda exc: self._handle_error("Freeze Weekly Schedule", exc), employee_id=self.employee.id, capability="schedule.manage")

    def _override_week(self):
        if not self.editable or self._week_status not in {EmployeeScheduleWeek.STATUS_PUBLISHED, EmployeeScheduleWeek.STATUS_FROZEN}: return
        reason, ok = QInputDialog.getText(self, "Re-open Schedule for Override", "Reason for changing this official schedule:")
        reason = reason.strip() if ok else ""
        if not reason: return
        if QMessageBox.question(self, "Confirm Schedule Override", "Re-open this official week as a new DRAFT revision? This action will be audited.") != QMessageBox.StandardButton.Yes: return
        execute_ui_operation(logger_obj=logger, operation="schedule.weekly.override", action=lambda: (self.service.reopen_week_for_override(self._week_start, reason), self.refresh_weekly()), on_error=lambda exc: self._handle_error("Schedule Override", exc), employee_id=self.employee.id, capability="schedule.manage")

    def _add_rule(self):
        if not self.editable: return
        dialog = ScheduleRuleDialog(self)
        if dialog.exec():
            execute_ui_operation(logger_obj=logger, operation="schedule.add_rule", action=lambda: (self.service.add_rule(self.employee.id, *dialog.values()), self.refresh_template()), on_error=lambda exc: self._handle_error("Schedule Template", exc), employee_id=self.employee.id, capability="schedule.manage")

    def _edit_rule(self):
        if not self.editable: return
        row = self.rules.currentRow()
        if row < 0: return
        rule_id = self.rules.item(row, 0).data(Qt.ItemDataRole.UserRole)
        def action():
            rule = next(item for item in self.service.list_rules(self.employee.id) if item.id == rule_id)
            dialog = ScheduleRuleDialog(self, rule)
            if dialog.exec():
                values = dialog.values()
                self.service.update_rule(rule_id, day_of_week=values[0], start_time=values[1], end_time=values[2], effective_from=values[3], effective_to=values[4], notes=values[5]); self.refresh_template()
        execute_ui_operation(logger_obj=logger, operation="schedule.edit_rule", action=action, on_error=lambda exc: self._handle_error("Schedule Template", exc), employee_id=self.employee.id, record_id=rule_id, capability="schedule.manage")

    def _delete_rule(self):
        if not self.editable: return
        row = self.rules.currentRow()
        if row < 0: return
        rule_id = self.rules.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Schedule Template", "Delete selected schedule rule?") == QMessageBox.StandardButton.Yes:
            execute_ui_operation(logger_obj=logger, operation="schedule.delete_rule", action=lambda: (self.service.delete_rule(rule_id), self.refresh_template()), on_error=lambda exc: self._handle_error("Schedule Template", exc), employee_id=self.employee.id, record_id=rule_id, capability="schedule.manage")

    def _add_exception(self):
        if not self.editable: return
        dialog = ScheduleExceptionDialog(self)
        if dialog.exec():
            execute_ui_operation(logger_obj=logger, operation="schedule.add_exception", action=lambda: (self.service.add_exception(self.employee.id, *dialog.values()), self.refresh_template()), on_error=lambda exc: self._handle_error("Schedule Template", exc), employee_id=self.employee.id, capability="schedule.manage")

    def _delete_exception(self):
        if not self.editable: return
        row = self.exceptions.currentRow()
        if row < 0: return
        exception_id = self.exceptions.item(row, 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Schedule Template", "Delete selected schedule exception?") == QMessageBox.StandardButton.Yes:
            execute_ui_operation(logger_obj=logger, operation="schedule.delete_exception", action=lambda: (self.service.delete_exception(exception_id), self.refresh_template()), on_error=lambda exc: self._handle_error("Schedule Template", exc), employee_id=self.employee.id, record_id=exception_id, capability="schedule.manage")
