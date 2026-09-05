from __future__ import annotations

import logging
from calendar import monthrange
from datetime import date
from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QComboBox, QDateEdit, QTimeEdit, QFormLayout, QLineEdit,
    QMessageBox, QGroupBox, QLabel, QDialog, QDialogButtonBox, QHeaderView
)
from centermanager.models.employee_working_time import EmployeeWorkingTimeEntry
from centermanager.ui.employee_workspace.error_boundary import execute_ui_operation

logger = logging.getLogger(__name__)


class WorkingTimeBookingDialog(QDialog):
    def __init__(self, parent=None, entry=None, default_date=None):
        super().__init__(parent); self.entry = entry
        self.setWindowTitle("Working Time"); self.setMinimumWidth(420)
        f = QFormLayout(self)
        self.day = QDateEdit(); self.day.setCalendarPopup(True); self.day.setDisplayFormat("dd/MM/yyyy")
        d = default_date or date.today(); self.day.setDate(QDate(d.year, d.month, d.day))
        self.start = QTimeEdit(); self.start.setDisplayFormat("HH:mm"); self.start.setTime(QTime(9, 0))
        self.end = QTimeEdit(); self.end.setDisplayFormat("HH:mm"); self.end.setTime(QTime(17, 0))
        self.typ = QComboBox(); self.typ.addItems(["WORK", "TEACHING", "MEETING", "TRAINING", "ADMIN", "OTHER"])
        self.notes = QLineEdit(); self.notes.setPlaceholderText("Optional")
        f.addRow("Date", self.day); f.addRow("Start", self.start); f.addRow("End", self.end); f.addRow("Work type", self.typ); f.addRow("Notes", self.notes)
        b = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
        if entry:
            self.day.setDate(QDate(entry.work_date.year, entry.work_date.month, entry.work_date.day)); self.start.setTime(QTime(entry.start_time.hour, entry.start_time.minute))
            if entry.end_time: self.end.setTime(QTime(entry.end_time.hour, entry.end_time.minute))
            self.typ.setCurrentText(entry.work_type); self.notes.setText(entry.notes or "")
    def values(self): return (self.day.date().toPython(), self.start.time().toPython(), self.end.time().toPython(), self.typ.currentText(), self.notes.text().strip() or None)


class EmployeeWorkingTimeWidget(QWidget):
    """Working-time booking, check-in/out and monthly summary."""
    def __init__(self, service, employee, editable=False, management=False, parent=None):
        super().__init__(parent); self.service = service; self.employee = employee; self.editable = bool(editable); self.management = bool(management); self._build(); self.refresh()
    def _build(self):
        root = QVBoxLayout(self); root.setContentsMargins(0, 0, 0, 0); root.setSpacing(10)
        top = QHBoxLayout(); self.month = QDateEdit(); self.month.setCalendarPopup(True); self.month.setDisplayFormat("MM/yyyy"); self.month.setDate(QDate.currentDate()); self.month.dateChanged.connect(self.refresh); top.addWidget(QLabel("Month")); top.addWidget(self.month); self.summary = QLabel("-"); top.addWidget(self.summary, 1)
        self.checkin = QPushButton("Check In"); self.checkout = QPushButton("Check Out"); self.add = QPushButton("Book Time"); self.edit = QPushButton("Edit"); self.delete = QPushButton("Delete")
        for b in (self.checkin, self.checkout): top.addWidget(b)
        if self.management:
            for b in (self.add, self.edit, self.delete): top.addWidget(b)
        root.addLayout(top)
        self.table = QTableWidget(0, 7); self.table.setHorizontalHeaderLabels(["Date", "Start", "End", "Hours", "Work Type", "Source", "Status"]); self.table.setMinimumHeight(260); self.table.verticalHeader().setDefaultSectionSize(30); [self.table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeMode.ResizeToContents) for c in range(6)]; self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeMode.Stretch); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); root.addWidget(self.table)
        self.checkin.clicked.connect(self._check_in); self.checkout.clicked.connect(self._check_out)
        if self.management:
            self.add.clicked.connect(self._add); self.edit.clicked.connect(self._edit); self.delete.clicked.connect(self._delete)
        self.set_editable(self.editable)
    def set_editable(self, enabled):
        self.editable = bool(enabled)
        for b in (self.checkin, self.checkout): b.setEnabled(self.editable)
        if self.management:
            for b in (self.add, self.edit, self.delete): b.setEnabled(self.editable)
    def _range(self):
        q = self.month.date(); y, m = q.year(), q.month(); return date(y, m, 1), date(y, m, monthrange(y, m)[1])
    def _handle_error(self, title, exc):
        QMessageBox.warning(self, title, f"Operation failed.\n\nReason: {exc}\n\nSee application log for technical details.")
    def refresh(self):
        def action():
            start, end = self._range(); rows = self.service.list_entries(self.employee.id, start, end)
            self.table.setRowCount(0); actual = 0
            for e in rows:
                i = self.table.rowCount(); self.table.insertRow(i); mins = self.service._minutes(e.start_time, e.end_time); actual += mins
                vals = [e.work_date.strftime("%d/%m/%Y"), e.start_time.strftime("%H:%M"), e.end_time.strftime("%H:%M") if e.end_time else "OPEN", f"{mins / 60:.2f}", e.work_type, e.source, e.status]
                for c, v in enumerate(vals): self.table.setItem(i, c, QTableWidgetItem(v))
                self.table.item(i, 0).setData(Qt.ItemDataRole.UserRole, e.id)
            sm = self.service.monthly_summary(self.employee.id, start.year, start.month)
            self.summary.setText(f"Actual {sm['actual_minutes']/60:.2f}h  •  Expected {sm['expected_minutes']/60:.2f}h  •  Overtime {sm['overtime_minutes']/60:.2f}h  •  Shortfall {sm['shortfall_minutes']/60:.2f}h")
            self.table.resizeColumnsToContents()
        execute_ui_operation(logger_obj=logger, operation="working_time.refresh", action=action, on_error=lambda exc: self._handle_error("Working Time", exc), employee_id=self.employee.id, capability="working_time.view")
    def _add(self):
        d = WorkingTimeBookingDialog(self, default_date=date.today())
        if d.exec():
            ok = execute_ui_operation(logger_obj=logger, operation="working_time.create_booking", action=lambda: self.service.create_booking(self.employee.id, *d.values()), on_error=lambda exc: self._handle_error("Working Time", exc), employee_id=self.employee.id, capability="working_time.manage")
            if ok: self.refresh()
    def _edit(self):
        i = self.table.currentRow()
        if i < 0: return
        eid = self.table.item(i, 0).data(Qt.ItemDataRole.UserRole)
        def action():
            entry = next(e for e in self.service.list_entries(self.employee.id) if e.id == eid); d = WorkingTimeBookingDialog(self, entry)
            if d.exec():
                vals = d.values(); self.service.update_booking(eid, work_date=vals[0], start_time=vals[1], end_time=vals[2], work_type=vals[3], notes=vals[4])
                return True
            return False
        if execute_ui_operation(logger_obj=logger, operation="working_time.update_booking", action=action, on_error=lambda exc: self._handle_error("Working Time", exc), employee_id=self.employee.id, record_id=eid, capability="working_time.manage"):
            self.refresh()
    def _delete(self):
        i = self.table.currentRow()
        if i < 0: return
        eid = self.table.item(i, 0).data(Qt.ItemDataRole.UserRole)
        if QMessageBox.question(self, "Delete working time", "Delete selected working-time entry?") == QMessageBox.StandardButton.Yes:
            if execute_ui_operation(logger_obj=logger, operation="working_time.delete_entry", action=lambda: self.service.delete_entry(eid), on_error=lambda exc: self._handle_error("Working Time", exc), employee_id=self.employee.id, record_id=eid, capability="working_time.manage"):
                self.refresh()
    def _check_in(self):
        if execute_ui_operation(logger_obj=logger, operation="working_time.check_in", action=lambda: self.service.check_in(self.employee.id), on_error=lambda exc: self._handle_error("Check In", exc), employee_id=self.employee.id, capability="working_time.create.self"):
            self.refresh()
    def _check_out(self):
        def action():
            rows = self.service.list_entries(self.employee.id, date.today(), date.today()); open_rows = [e for e in rows if e.status == EmployeeWorkingTimeEntry.STATUS_OPEN]
            if not open_rows: raise ValueError("No open working-time entry to check out.")
            if len(open_rows) > 1: raise ValueError("Multiple open working-time entries were found; check-out was blocked to protect data integrity.")
            self.service.check_out(open_rows[0].id)
        if execute_ui_operation(logger_obj=logger, operation="working_time.check_out", action=action, on_error=lambda exc: self._handle_error("Check Out", exc), employee_id=self.employee.id, capability="working_time.create.self"):
            self.refresh()
