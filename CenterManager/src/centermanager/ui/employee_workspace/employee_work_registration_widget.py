from __future__ import annotations
from calendar import monthrange
from datetime import date
from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QDialog, QDialogButtonBox, QComboBox, QDateEdit, QTimeEdit,
    QFormLayout, QLineEdit, QMessageBox, QLabel, QHeaderView
)
from centermanager.models.employee_work_registration import EmployeeWorkRegistration

class WorkRegistrationDialog(QDialog):
    def __init__(self,parent=None,entry=None,default_date=None):
        super().__init__(parent); self.setWindowTitle("Register Availability"); self.setMinimumWidth(430)
        f=QFormLayout(self)
        self.day=QDateEdit(); self.day.setCalendarPopup(True); self.day.setDisplayFormat("dd/MM/yyyy")
        d=default_date or date.today(); self.day.setDate(QDate(d.year,d.month,d.day))
        self.start=QTimeEdit(); self.start.setDisplayFormat("HH:mm"); self.start.setTime(QTime(9,0))
        self.end=QTimeEdit(); self.end.setDisplayFormat("HH:mm"); self.end.setTime(QTime(17,0))
        self.typ=QComboBox(); self.typ.addItems(["WORK","TEACHING","MEETING","TRAINING","ADMIN","OTHER"])
        self.notes=QLineEdit(); self.notes.setPlaceholderText("Optional note")
        f.addRow("Available date",self.day); f.addRow("From",self.start); f.addRow("To",self.end); f.addRow("Work type",self.typ); f.addRow("Note",self.notes)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
        if entry:
            self.day.setDate(QDate(entry.work_date.year,entry.work_date.month,entry.work_date.day)); self.start.setTime(QTime(entry.start_time.hour,entry.start_time.minute)); self.end.setTime(QTime(entry.end_time.hour,entry.end_time.minute)); self.typ.setCurrentText(entry.work_type); self.notes.setText(entry.notes or "")
    def values(self): return self.day.date().toPython(),self.start.time().toPython(),self.end.time().toPython(),self.typ.currentText(),self.notes.text().strip() or None

class EmployeeWorkRegistrationWidget(QWidget):
    """Employee's proposed availability for the next calendar month."""
    def __init__(self,service,employee,editable=False,parent=None):
        super().__init__(parent); self.service=service; self.employee=employee; self.editable=bool(editable); self._build(); self.refresh()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(28,24,28,24); root.setSpacing(12)
        self.title=QLabel("Work Registration"); self.title.setStyleSheet("font-size:24px;font-weight:700;"); root.addWidget(self.title)
        self.info=QLabel("Register the times you are available to work next month. This is an input for manager planning; it is not attendance."); self.info.setWordWrap(True); self.info.setStyleSheet("color:#68737d;"); root.addWidget(self.info)
        bar=QHBoxLayout(); self.month=QLabel(); self.month.setStyleSheet("font-weight:600;font-size:15px;"); bar.addWidget(self.month); bar.addStretch()
        self.status=QLabel(); self.status.setStyleSheet("font-weight:600;"); bar.addWidget(self.status)
        root.addLayout(bar)
        actions=QHBoxLayout(); self.add=QPushButton("+ Add Availability"); self.edit=QPushButton("Edit"); self.delete=QPushButton("Delete"); self.submit=QPushButton("Submit for Planning")
        for b in (self.add,self.edit,self.delete,self.submit): actions.addWidget(b)
        actions.addStretch(); root.addLayout(actions)
        self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(["Date","From","To","Hours","Work Type","Status"]); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.verticalHeader().setVisible(False); self.table.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.ResizeToContents); self.table.horizontalHeader().setSectionResizeMode(4,QHeaderView.ResizeMode.Stretch); self.table.horizontalHeader().setSectionResizeMode(5,QHeaderView.ResizeMode.ResizeToContents); root.addWidget(self.table,1)
        self.add.clicked.connect(self._add); self.edit.clicked.connect(self._edit); self.delete.clicked.connect(self._delete); self.submit.clicked.connect(self._submit_month); self.table.itemSelectionChanged.connect(self._update_actions)
        self.set_editable(self.editable)
    def _range(self): y,m=self.service.next_month(); return y,m,date(y,m,1),date(y,m,monthrange(y,m)[1])
    def set_editable(self,enabled): self.editable=bool(enabled); self._update_actions()
    def _update_actions(self):
        row=self.table.currentRow(); has=row>=0; draft=has and self.table.item(row,5) and self.table.item(row,5).text()==EmployeeWorkRegistration.STATUS_DRAFT
        submitted = any(self.table.item(i,5) and self.table.item(i,5).text() == EmployeeWorkRegistration.STATUS_SUBMITTED for i in range(self.table.rowCount()))
        closed = any(self.table.item(i,5) and self.table.item(i,5).text() == EmployeeWorkRegistration.STATUS_CLOSED for i in range(self.table.rowCount()))
        month_editable = self.editable and not submitted and not closed
        self.add.setEnabled(month_editable); self.edit.setEnabled(month_editable and draft); self.delete.setEnabled(month_editable and draft)
        has_draft=any(self.table.item(i,5) and self.table.item(i,5).text()==EmployeeWorkRegistration.STATUS_DRAFT for i in range(self.table.rowCount()))
        self.submit.setEnabled(self.editable and has_draft)
    def refresh(self):
        try:
            y,m,start,end=self._range(); rows=self.service.list_for_employee(self.employee.id,y,m); self.month.setText(f"Registration month: {m:02d}/{y}  •  Next month")
            statuses={r.status for r in rows}; current="SUBMITTED" if EmployeeWorkRegistration.STATUS_SUBMITTED in statuses else ("CLOSED" if statuses and statuses=={EmployeeWorkRegistration.STATUS_CLOSED} else "DRAFT")
            self.status.setText(f"Status: {current}"); self.table.setRowCount(0)
            for r in rows:
                i=self.table.rowCount(); self.table.insertRow(i); mins=(r.end_time.hour*60+r.end_time.minute)-(r.start_time.hour*60+r.start_time.minute); vals=[r.work_date.strftime("%d/%m/%Y"),r.start_time.strftime("%H:%M"),r.end_time.strftime("%H:%M"),f"{mins/60:.2f}",r.work_type,r.status]
                for c,v in enumerate(vals): self.table.setItem(i,c,QTableWidgetItem(v))
                self.table.item(i,0).setData(Qt.ItemDataRole.UserRole,r.id)
            self._update_actions()
        except Exception as exc: QMessageBox.warning(self,"Work Registration",f"Could not load registration.\n\n{exc}")
    def _selected(self):
        i=self.table.currentRow()
        if i<0:return None
        rid=self.table.item(i,0).data(Qt.ItemDataRole.UserRole); y,m=self.service.next_month(); return next((r for r in self.service.list_for_employee(self.employee.id,y,m) if r.id==rid),None)
    def _add(self):
        y,m=self.service.next_month(); d=WorkRegistrationDialog(self,default_date=date(y,m,1))
        if d.exec():
            try:self.service.create(self.employee.id,*d.values()); self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Work Registration",str(exc))
    def _edit(self):
        r=self._selected()
        if not r:return
        d=WorkRegistrationDialog(self,r)
        if d.exec():
            try:
                v=d.values(); self.service.update(r.id,work_date=v[0],start_time=v[1],end_time=v[2],work_type=v[3],notes=v[4]); self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Work Registration",str(exc))
    def _delete(self):
        r=self._selected()
        if not r:return
        if QMessageBox.question(self,"Delete availability","Delete selected availability block?")==QMessageBox.StandardButton.Yes:
            try:self.service.delete(r.id); self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Work Registration",str(exc))
    def _submit_month(self):
        y,m=self.service.next_month()
        if QMessageBox.question(self,"Submit availability",f"Submit all availability blocks for {m:02d}/{y} to the manager for planning?")==QMessageBox.StandardButton.Yes:
            try:self.service.submit_month(self.employee.id,y,m); self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Work Registration",str(exc))
