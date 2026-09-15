from __future__ import annotations

import logging

from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QDialogButtonBox, QComboBox, QDateEdit, QTimeEdit,
    QFormLayout, QLineEdit, QMessageBox, QGroupBox, QCheckBox, QHeaderView,
)
from centermanager.models.employee_schedule import VALID_EXCEPTION_TYPES
from centermanager.ui.employee_workspace.error_boundary import execute_ui_operation

logger = logging.getLogger(__name__)
DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


class ScheduleRuleDialog(QDialog):
    def __init__(self, parent=None, rule=None):
        super().__init__(parent); self.rule = rule; self.setWindowTitle("Schedule Rule"); self.setMinimumWidth(420)
        f = QFormLayout(self); self.day = QComboBox(); self.day.addItems(DAYS)
        self.start = QTimeEdit(); self.start.setDisplayFormat("HH:mm"); self.start.setTime(QTime(9, 0))
        self.end = QTimeEdit(); self.end.setDisplayFormat("HH:mm"); self.end.setTime(QTime(17, 0))
        self.frm = QDateEdit(); self.frm.setCalendarPopup(True); self.frm.setDisplayFormat("dd/MM/yyyy"); self.frm.setDate(QDate.currentDate())
        self.to = QDateEdit(); self.to.setCalendarPopup(True); self.to.setDisplayFormat("dd/MM/yyyy"); self.to.setDate(QDate.currentDate())
        self.no_end = QCheckBox("No end date"); self.no_end.setChecked(True); self.notes = QLineEdit(); self.notes.setPlaceholderText("Optional")
        f.addRow("Day", self.day); f.addRow("Start", self.start); f.addRow("End", self.end); f.addRow("Effective from", self.frm); f.addRow("Effective to", self.to); f.addRow("", self.no_end); f.addRow("Notes", self.notes)
        b = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
        if rule:
            self.day.setCurrentIndex(rule.day_of_week); self.start.setTime(QTime(rule.start_time.hour, rule.start_time.minute)); self.end.setTime(QTime(rule.end_time.hour, rule.end_time.minute)); self.frm.setDate(QDate(rule.effective_from.year, rule.effective_from.month, rule.effective_from.day)); self.notes.setText(rule.notes or "")
            if rule.effective_to: self.to.setDate(QDate(rule.effective_to.year, rule.effective_to.month, rule.effective_to.day)); self.no_end.setChecked(False)
            else: self.no_end.setChecked(True)
    def values(self):
        frm = self.frm.date().toPython(); to = self.to.date().toPython()
        if self.no_end.isChecked(): to = None
        return self.day.currentIndex(), self.start.time().toPython(), self.end.time().toPython(), frm, to, self.notes.text().strip() or None


class ScheduleExceptionDialog(QDialog):
    def __init__(self, parent=None, exception=None):
        super().__init__(parent); self.setWindowTitle("Schedule Exception"); self.setMinimumWidth(420)
        f = QFormLayout(self); self.day = QDateEdit(); self.day.setCalendarPopup(True); self.day.setDisplayFormat("dd/MM/yyyy"); self.day.setDate(QDate.currentDate())
        self.typ = QComboBox(); self.typ.addItems(sorted(VALID_EXCEPTION_TYPES)); self.start = QTimeEdit(); self.start.setDisplayFormat("HH:mm"); self.start.setTime(QTime(9, 0)); self.end = QTimeEdit(); self.end.setDisplayFormat("HH:mm"); self.end.setTime(QTime(17, 0)); self.notes = QLineEdit()
        f.addRow("Date", self.day); f.addRow("Type", self.typ); f.addRow("Start", self.start); f.addRow("End", self.end); f.addRow("Notes", self.notes)
        b = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b); self.typ.currentTextChanged.connect(self._toggle)
        if exception:
            self.day.setDate(QDate(exception.schedule_date.year, exception.schedule_date.month, exception.schedule_date.day)); self.typ.setCurrentText(exception.exception_type); self.notes.setText(exception.notes or "")
            if exception.start_time: self.start.setTime(QTime(exception.start_time.hour, exception.start_time.minute))
            if exception.end_time: self.end.setTime(QTime(exception.end_time.hour, exception.end_time.minute))
        self._toggle(self.typ.currentText())
    def _toggle(self, t): self.start.setEnabled(t == "MODIFIED"); self.end.setEnabled(t == "MODIFIED")
    def values(self): return self.day.date().toPython(), self.typ.currentText(), self.start.time().toPython(), self.end.time().toPython(), self.notes.text().strip() or None


class EmployeeScheduleWidget(QWidget):
    """Compact schedule management/read-only view used inside Employee Profile."""
    def __init__(self, service, employee, editable=False, parent=None):
        super().__init__(parent); self.service = service; self.employee = employee; self.editable = bool(editable); self._build(); self.refresh()
    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0)
        rules_box = QGroupBox("Weekly Schedule"); rl = QVBoxLayout(rules_box); self.rules = QTableWidget(0, 5); self.rules.setHorizontalHeaderLabels(["Day", "Time", "Effective from", "Effective to", "Notes"]); self.rules.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.rules.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.rules.setMinimumHeight(190); self.rules.verticalHeader().setDefaultSectionSize(32); [self.rules.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents) for c in range(4)]; self.rules.horizontalHeader().setSectionResizeMode(4, QHeaderView.ResizeMode.Stretch); rl.addWidget(self.rules)
        rb = QHBoxLayout(); self.add_rule = QPushButton("Add"); self.edit_rule = QPushButton("Edit"); self.del_rule = QPushButton("Delete"); rb.addWidget(self.add_rule); rb.addWidget(self.edit_rule); rb.addWidget(self.del_rule); rb.addStretch(); rl.addLayout(rb); root.addWidget(rules_box)
        ex_box = QGroupBox("Schedule Exceptions"); el = QVBoxLayout(ex_box); self.exceptions = QTableWidget(0, 4); self.exceptions.setHorizontalHeaderLabels(["Date", "Type", "Time", "Notes"]); self.exceptions.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.exceptions.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.exceptions.setMinimumHeight(150); self.exceptions.verticalHeader().setDefaultSectionSize(32); [self.exceptions.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents) for c in range(3)]; self.exceptions.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch); el.addWidget(self.exceptions); eb = QHBoxLayout(); self.add_ex = QPushButton("Add Exception"); self.del_ex = QPushButton("Delete"); eb.addWidget(self.add_ex); eb.addWidget(self.del_ex); eb.addStretch(); el.addLayout(eb); root.addWidget(ex_box)
        self.add_rule.clicked.connect(self._add_rule); self.edit_rule.clicked.connect(self._edit_rule); self.del_rule.clicked.connect(self._delete_rule); self.add_ex.clicked.connect(self._add_exception); self.del_ex.clicked.connect(self._delete_exception)
        self.set_editable(self.editable)
    def set_editable(self, enabled):
        self.editable = bool(enabled)
        for b in (self.add_rule, self.edit_rule, self.del_rule, self.add_ex, self.del_ex): b.setEnabled(self.editable)
    def _handle_error(self, title, exc):
        QMessageBox.warning(self, title, f"Operation failed.\n\nReason: {exc}\n\nSee application log for technical details.")
    def refresh(self):
        def action():
            rules = self.service.list_rules(self.employee.id); self.rules.setRowCount(0)
            for r in rules:
                i = self.rules.rowCount(); self.rules.insertRow(i); self.rules.setItem(i, 0, QTableWidgetItem(DAYS[r.day_of_week])); self.rules.setItem(i, 1, QTableWidgetItem(f"{r.start_time:%H:%M} – {r.end_time:%H:%M}")); self.rules.setItem(i, 2, QTableWidgetItem(r.effective_from.strftime("%d/%m/%Y"))); self.rules.setItem(i, 3, QTableWidgetItem(r.effective_to.strftime("%d/%m/%Y") if r.effective_to else "Open-ended")); self.rules.setItem(i, 4, QTableWidgetItem(r.notes or "")); self.rules.item(i, 0).setData(Qt.ItemDataRole.UserRole, r.id)
            ex = self.service.list_exceptions(self.employee.id); self.exceptions.setRowCount(0)
            for x in ex:
                i = self.exceptions.rowCount(); self.exceptions.insertRow(i); self.exceptions.setItem(i, 0, QTableWidgetItem(x.schedule_date.strftime("%d/%m/%Y"))); self.exceptions.setItem(i, 1, QTableWidgetItem(x.exception_type)); self.exceptions.setItem(i, 2, QTableWidgetItem(f"{x.start_time:%H:%M} – {x.end_time:%H:%M}" if x.start_time and x.end_time else "—")); self.exceptions.setItem(i, 3, QTableWidgetItem(x.notes or "")); self.exceptions.item(i, 0).setData(Qt.ItemDataRole.UserRole, x.id)
            self.rules.resizeColumnsToContents(); self.exceptions.resizeColumnsToContents()
        execute_ui_operation(logger_obj=logger, operation="schedule.refresh", action=action, on_error=lambda exc: self._handle_error("Schedule", exc), employee_id=self.employee.id, capability="schedule.view")
    def _add_rule(self):
        d = ScheduleRuleDialog(self)
        if d.exec(): execute_ui_operation(logger_obj=logger, operation="schedule.add_rule", action=lambda: (self.service.add_rule(self.employee.id, *d.values()), self.refresh()), on_error=lambda exc: self._handle_error("Schedule", exc), employee_id=self.employee.id, capability="schedule.manage")
    def _edit_rule(self):
        i = self.rules.currentRow()
        if i < 0: return
        rid = self.rules.item(i, 0).data(Qt.ItemDataRole.UserRole)
        def action():
            rule = next(r for r in self.service.list_rules(self.employee.id) if r.id == rid); d = ScheduleRuleDialog(self, rule)
            if d.exec():
                values = d.values(); self.service.update_rule(rid, day_of_week=values[0], start_time=values[1], end_time=values[2], effective_from=values[3], effective_to=values[4], notes=values[5]); self.refresh()
        execute_ui_operation(logger_obj=logger, operation="schedule.edit_rule", action=action, on_error=lambda exc: self._handle_error("Schedule", exc), employee_id=self.employee.id, record_id=rid, capability="schedule.manage")
    def _delete_rule(self):
        i = self.rules.currentRow()
        if i < 0: return
        rid = self.rules.item(i, 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Delete schedule", "Delete selected schedule rule?") == QMessageBox.StandardButton.Yes: execute_ui_operation(logger_obj=logger, operation="schedule.delete_rule", action=lambda: (self.service.delete_rule(rid), self.refresh()), on_error=lambda exc: self._handle_error("Schedule", exc), employee_id=self.employee.id, record_id=rid, capability="schedule.manage")
    def _add_exception(self):
        d = ScheduleExceptionDialog(self)
        if d.exec(): execute_ui_operation(logger_obj=logger, operation="schedule.add_exception", action=lambda: (self.service.add_exception(self.employee.id, *d.values()), self.refresh()), on_error=lambda exc: self._handle_error("Schedule", exc), employee_id=self.employee.id, capability="schedule.manage")
    def _delete_exception(self):
        i = self.exceptions.currentRow()
        if i < 0: return
        xid = self.exceptions.item(i, 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Delete exception", "Delete selected exception?") == QMessageBox.StandardButton.Yes: execute_ui_operation(logger_obj=logger, operation="schedule.delete_exception", action=lambda: (self.service.delete_exception(xid), self.refresh()), on_error=lambda exc: self._handle_error("Schedule", exc), employee_id=self.employee.id, record_id=xid, capability="schedule.manage")
