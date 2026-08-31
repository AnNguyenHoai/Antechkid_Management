from __future__ import annotations
from calendar import monthrange
from datetime import date
from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox,QDialog,QDialogButtonBox,QComboBox,QDateEdit,QTimeEdit,QFormLayout,QLineEdit
from centermanager.models.employee_work_registration import EmployeeWorkRegistration

class WorkRegistrationDialog(QDialog):
    def __init__(self,parent=None,entry=None,default_date=None):
        super().__init__(parent); self.setWindowTitle("Register Availability"); self.setMinimumWidth(430); f=QFormLayout(self)
        self.day=QDateEdit(); self.day.setCalendarPopup(True); self.day.setDisplayFormat("dd/MM/yyyy"); d=default_date or date.today(); self.day.setDate(QDate(d.year,d.month,d.day))
        self.start=QTimeEdit(); self.start.setDisplayFormat("HH:mm"); self.start.setTime(QTime(9,0)); self.end=QTimeEdit(); self.end.setDisplayFormat("HH:mm"); self.end.setTime(QTime(17,0)); self.typ=QComboBox(); self.typ.addItems(["WORK","TEACHING","MEETING","TRAINING","ADMIN","OTHER"]); self.notes=QLineEdit(); self.notes.setPlaceholderText("Optional note")
        for label,w in (("Available date",self.day),("From",self.start),("To",self.end),("Work type",self.typ),("Note",self.notes)): f.addRow(label,w)
        b=QDialogButtonBox(QDialogButtonBox.Save|QDialogButtonBox.Cancel); b.accepted.connect(self.accept); b.rejected.connect(self.reject); f.addRow(b)
        if entry:
            self.day.setDate(QDate(entry.work_date.year,entry.work_date.month,entry.work_date.day)); self.start.setTime(QTime(entry.start_time.hour,entry.start_time.minute)); self.end.setTime(QTime(entry.end_time.hour,entry.end_time.minute)); self.typ.setCurrentText(entry.work_type); self.notes.setText(entry.notes or "")
    def values(self): return self.day.date().toPython(),self.start.time().toPython(),self.end.time().toPython(),self.typ.currentText(),self.notes.text().strip() or None

class EmployeeWorkRegistrationWidget(QWidget):
    """One monthly registration aggregate with child availability blocks."""
    def __init__(self,service,employee,editable=False,parent=None):
        super().__init__(parent); self.service=service; self.employee=employee; self.editable=bool(editable); self.registration=None; self._build(); self.refresh()
    def _build(self):
        root=QVBoxLayout(self); root.setContentsMargins(28,24,28,24); root.setSpacing(12); self.title=QLabel("Work Registration"); self.title.setStyleSheet("font-size:24px;font-weight:700;"); root.addWidget(self.title)
        self.info=QLabel("Register availability for next month. All availability blocks belong to one monthly registration."); self.info.setWordWrap(True); self.info.setStyleSheet("color:#68737d;"); root.addWidget(self.info)
        bar=QHBoxLayout(); self.month=QLabel(); self.month.setStyleSheet("font-weight:600;font-size:15px;"); bar.addWidget(self.month); bar.addStretch(); self.status=QLabel(); self.status.setStyleSheet("font-weight:600;"); bar.addWidget(self.status); root.addLayout(bar)
        actions=QHBoxLayout(); self.add=QPushButton("+ Add Availability"); self.edit=QPushButton("Edit"); self.delete=QPushButton("Delete"); self.submit=QPushButton("Submit for Planning"); [actions.addWidget(b) for b in (self.add,self.edit,self.delete,self.submit)]; actions.addStretch(); root.addLayout(actions)
        self.table=QTableWidget(0,6); self.table.setHorizontalHeaderLabels(["Date","From","To","Hours","Work Type","Notes"]); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.verticalHeader().setVisible(False); h=self.table.horizontalHeader(); [h.setSectionResizeMode(c,QHeaderView.ResizeMode.ResizeToContents) for c in range(5)]; h.setSectionResizeMode(5,QHeaderView.ResizeMode.Stretch); root.addWidget(self.table,1)
        self.add.clicked.connect(self._add); self.edit.clicked.connect(self._edit); self.delete.clicked.connect(self._delete); self.submit.clicked.connect(self._submit_month); self.table.itemSelectionChanged.connect(self._update_actions); self.set_editable(self.editable)
    def _range(self): y,m=self.service.next_month(); return y,m,date(y,m,1),date(y,m,monthrange(y,m)[1])
    def set_editable(self,enabled): self.editable=bool(enabled); self._update_actions()
    def _update_actions(self):
        draft=bool(self.registration and self.registration.status==EmployeeWorkRegistration.STATUS_DRAFT); has=self.table.currentRow()>=0; e=self.editable and draft; self.add.setEnabled(e); self.edit.setEnabled(e and has); self.delete.setEnabled(e and has); self.submit.setEnabled(e and bool(self.registration and self.registration.blocks))
    def refresh(self):
        try:
            y,m,_,_=self._range(); self.month.setText(f"Registration month: {m:02d}/{y} • Next month"); self.registration=self.service.list_for_employee(self.employee.id,y,m); self.status.setText(f"Status: {self.registration.status if self.registration else 'DRAFT'}"); self.table.setRowCount(0)
            if self.registration:
                for b in self.registration.blocks:
                    i=self.table.rowCount(); self.table.insertRow(i); mins=(b.end_time.hour*60+b.end_time.minute)-(b.start_time.hour*60+b.start_time.minute); vals=[b.work_date.strftime("%d/%m/%Y"),b.start_time.strftime("%H:%M"),b.end_time.strftime("%H:%M"),f"{mins/60:.2f}",b.work_type,b.notes or ""]
                    for c,v in enumerate(vals): self.table.setItem(i,c,QTableWidgetItem(v))
                    self.table.item(i,0).setData(Qt.ItemDataRole.UserRole,b.id)
            self._update_actions()
        except Exception as exc: QMessageBox.warning(self,"Work Registration",f"Could not load registration.\n\n{exc}")
    def _selected(self):
        i=self.table.currentRow();
        if i<0 or not self.registration:return None
        bid=self.table.item(i,0).data(Qt.ItemDataRole.UserRole); return next((b for b in self.registration.blocks if b.id==bid),None)
    def _add(self):
        y,m=self.service.next_month(); d=WorkRegistrationDialog(self,default_date=date(y,m,1));
        if d.exec():
            try:self.service.create(self.employee.id,*d.values()); self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Work Registration",str(exc))
    def _edit(self):
        b=self._selected();
        if not b:return
        d=WorkRegistrationDialog(self,b)
        if d.exec():
            try:v=d.values(); self.service.update(b.id,work_date=v[0],start_time=v[1],end_time=v[2],work_type=v[3],notes=v[4]); self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Work Registration",str(exc))
    def _delete(self):
        b=self._selected();
        if not b:return
        if QMessageBox.question(self,"Delete availability","Delete selected availability block?")==QMessageBox.StandardButton.Yes:
            try:self.service.delete(b.id); self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Work Registration",str(exc))
    def _submit_month(self):
        y,m=self.service.next_month()
        if QMessageBox.question(self,"Submit availability",f"Submit the complete {m:02d}/{y} availability to the manager?")==QMessageBox.StandardButton.Yes:
            try:self.service.submit_month(self.employee.id,y,m); self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Work Registration",str(exc))
