from __future__ import annotations
from calendar import monthrange
from datetime import date
from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QTableWidget,QTableWidgetItem,QPushButton,QDialog,QDialogButtonBox,QComboBox,QDateEdit,QTimeEdit,QFormLayout,QLineEdit,QMessageBox,QLabel,QGroupBox
from centermanager.models.employee_work_registration import EmployeeWorkRegistration

class WorkRegistrationDialog(QDialog):
    def __init__(self,parent=None,entry=None,default_date=None):
        super().__init__(parent); self.setWindowTitle("Register Working Time"); self.setMinimumWidth(430)
        f=QFormLayout(self)
        self.day=QDateEdit();self.day.setCalendarPopup(True);self.day.setDisplayFormat("dd/MM/yyyy")
        d=default_date or date.today(); self.day.setDate(QDate(d.year,d.month,d.day))
        self.start=QTimeEdit();self.start.setDisplayFormat("HH:mm");self.start.setTime(QTime(9,0))
        self.end=QTimeEdit();self.end.setDisplayFormat("HH:mm");self.end.setTime(QTime(17,0))
        self.typ=QComboBox();self.typ.addItems(["WORK","TEACHING","MEETING","TRAINING","ADMIN","OTHER"])
        self.notes=QLineEdit();self.notes.setPlaceholderText("Optional")
        f.addRow("Date",self.day);f.addRow("Start",self.start);f.addRow("End",self.end);f.addRow("Work type",self.typ);f.addRow("Notes",self.notes)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel);b.accepted.connect(self.accept);b.rejected.connect(self.reject);f.addRow(b)
        if entry:
            self.day.setDate(QDate(entry.work_date.year,entry.work_date.month,entry.work_date.day));self.start.setTime(QTime(entry.start_time.hour,entry.start_time.minute));self.end.setTime(QTime(entry.end_time.hour,entry.end_time.minute));self.typ.setCurrentText(entry.work_type);self.notes.setText(entry.notes or "")
    def values(self): return self.day.date().toPython(),self.start.time().toPython(),self.end.time().toPython(),self.typ.currentText(),self.notes.text().strip() or None

class EmployeeWorkRegistrationWidget(QWidget):
    """Self-service proposed working schedule for the next calendar month."""
    def __init__(self,service,employee,editable=False,parent=None):
        super().__init__(parent);self.service=service;self.employee=employee;self.editable=bool(editable);self._build();self.refresh()
    def _build(self):
        root=QVBoxLayout(self);root.setContentsMargins(28,24,28,24);root.setSpacing(12)
        title=QLabel("Working Time Registration");title.setStyleSheet("font-size:24px;font-weight:700;");root.addWidget(title)
        self.info=QLabel();self.info.setStyleSheet("font-size:14px;");root.addWidget(self.info)
        bar=QHBoxLayout();self.month=QLabel();bar.addWidget(self.month);bar.addStretch();self.add=QPushButton("Add Time");self.edit=QPushButton("Edit");self.delete=QPushButton("Delete");self.submit=QPushButton("Submit Registration");
        for b in (self.add,self.edit,self.delete,self.submit):bar.addWidget(b)
        root.addLayout(bar)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(["Date","Start","End","Hours","Work Type","Status"]);self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);root.addWidget(self.table,1)
        self.add.clicked.connect(self._add);self.edit.clicked.connect(self._edit);self.delete.clicked.connect(self._delete);self.submit.clicked.connect(self._submit)
        self.set_editable(self.editable)
    def _range(self):
        y,m=self.service.next_month();return date(y,m,1),date(y,m,monthrange(y,m)[1])
    def set_editable(self,enabled):
        self.editable=bool(enabled)
        for b in (self.add,self.edit,self.delete,self.submit):b.setEnabled(self.editable)
    def refresh(self):
        try:
            y,m=self.service.next_month();self.month.setText(f"Registration month: {m:02d}/{y} (next month)")
            start,end=self._range();rows=self.service.list_for_employee(self.employee.id,y,m)
            self.table.setRowCount(0)
            for r in rows:
                i=self.table.rowCount();self.table.insertRow(i);mins=int((r.end_time.hour*60+r.end_time.minute)-(r.start_time.hour*60+r.start_time.minute));vals=[r.work_date.strftime("%d/%m/%Y"),r.start_time.strftime("%H:%M"),r.end_time.strftime("%H:%M"),f"{mins/60:.2f}",r.work_type,r.status]
                for c,v in enumerate(vals):self.table.setItem(i,c,QTableWidgetItem(v))
                self.table.item(i,0).setData(Qt.ItemDataRole.UserRole,r.id)
            self.table.resizeColumnsToContents();self.info.setText("Register your expected working time for the coming month. This is separate from actual Attendance and does not create attendance records.")
        except Exception as exc:QMessageBox.warning(self,"Working Time Registration",f"Could not load registration.\n\n{exc}")
    def _selected(self):
        i=self.table.currentRow();
        if i<0:return None
        rid=self.table.item(i,0).data(Qt.ItemDataRole.UserRole)
        y,m=self.service.next_month();return next((r for r in self.service.list_for_employee(self.employee.id,y,m) if r.id==rid),None)
    def _add(self):
        y,m=self.service.next_month();d=WorkRegistrationDialog(self,default_date=date(y,m,1))
        if d.exec():
            try:self.service.create(self.employee.id,*d.values());self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Working Time Registration",str(exc))
    def _edit(self):
        r=self._selected()
        if not r:return
        d=WorkRegistrationDialog(self,r)
        if d.exec():
            try:self.service.update(r.id,work_date=d.values()[0],start_time=d.values()[1],end_time=d.values()[2],work_type=d.values()[3],notes=d.values()[4]);self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Working Time Registration",str(exc))
    def _delete(self):
        r=self._selected()
        if not r:return
        if QMessageBox.question(self,"Delete registration","Delete selected registration?")==QMessageBox.StandardButton.Yes:
            try:self.service.delete(r.id);self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Working Time Registration",str(exc))
    def _submit(self):
        r=self._selected()
        if not r:return
        try:self.service.submit(r.id);self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Working Time Registration",str(exc))
