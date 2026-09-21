from __future__ import annotations

import logging
from datetime import date, timedelta
from PySide6.QtCore import QDate, QTime, Qt
from PySide6.QtWidgets import QComboBox,QDateEdit,QDialog,QDialogButtonBox,QFormLayout,QGridLayout,QGroupBox,QHBoxLayout,QHeaderView,QLabel,QLineEdit,QMessageBox,QPushButton,QTableWidget,QTableWidgetItem,QTimeEdit,QVBoxLayout,QWidget
from centermanager.models.employee_work_registration import EmployeeWorkRegistration
logger=logging.getLogger(__name__)

class WorkRegistrationDialog(QDialog):
    def __init__(self,parent=None,entry=None,default_date=None,min_date=None,max_date=None):
        super().__init__(parent);self.setWindowTitle("Register Availability" if entry is None else "Edit Availability");self.setMinimumWidth(430);form=QFormLayout(self)
        self.day=QDateEdit();self.day.setCalendarPopup(True);self.day.setDisplayFormat("dd/MM/yyyy");d=default_date or date.today();self.day.setDate(QDate(d.year,d.month,d.day))
        if min_date:self.day.setMinimumDate(QDate(min_date.year,min_date.month,min_date.day))
        if max_date:self.day.setMaximumDate(QDate(max_date.year,max_date.month,max_date.day))
        self.start=QTimeEdit();self.start.setDisplayFormat("HH:mm");self.start.setTime(QTime(9,0));self.end=QTimeEdit();self.end.setDisplayFormat("HH:mm");self.end.setTime(QTime(17,0));self.typ=QComboBox();self.typ.addItems(["WORK","TEACHING","MEETING","TRAINING","ADMIN","OTHER"]);self.notes=QLineEdit();self.notes.setMaxLength(500);self.notes.setPlaceholderText("Optional note")
        for label,widget in (("Available date",self.day),("From",self.start),("To",self.end),("Work type",self.typ),("Note",self.notes)):form.addRow(label,widget)
        buttons=QDialogButtonBox(QDialogButtonBox.StandardButton.Save|QDialogButtonBox.StandardButton.Cancel);buttons.accepted.connect(self._accept_if_valid);buttons.rejected.connect(self.reject);form.addRow(buttons)
        if entry:self.day.setDate(QDate(entry.work_date.year,entry.work_date.month,entry.work_date.day));self.start.setTime(QTime(entry.start_time.hour,entry.start_time.minute));self.end.setTime(QTime(entry.end_time.hour,entry.end_time.minute));self.typ.setCurrentText(entry.work_type);self.notes.setText(entry.notes or "")
    def _accept_if_valid(self):
        if self.start.time()>=self.end.time():QMessageBox.warning(self,"Invalid availability","End time must be after start time.");return
        self.accept()
    def values(self):return self.day.date().toPython(),self.start.time().toPython(),self.end.time().toPython(),self.typ.currentText(),self.notes.text().strip() or None

class EmployeeWorkRegistrationWidget(QWidget):
    """Employee self-service weekly availability registration."""
    def __init__(self,service,employee,editable=False,parent=None):
        super().__init__(parent);self.service=service;self.employee=employee;self.editable=bool(editable);self.registration=None;self._last_error=None;self._setup();self.refresh()
    def _setup(self):
        root=QVBoxLayout(self);root.setContentsMargins(28,24,28,24);root.setSpacing(16);title=QLabel("My Work Registration");title.setStyleSheet("font-size:24px;font-weight:700;");root.addWidget(title);desc=QLabel("Register the days and time ranges you are available to work next week. Your registration is submitted as one weekly request for manager planning.");desc.setWordWrap(True);desc.setStyleSheet("color:#68737d;");root.addWidget(desc)
        summary=QGroupBox("Registration Summary");grid=QGridLayout(summary);self.week=QLabel("-");self.status=QLabel("-");self.blocks_summary=QLabel("0 blocks");self.hours_summary=QLabel("0.00 hours");self.deadline_summary=QLabel("-");self.status.setStyleSheet("font-weight:700;");grid.addWidget(QLabel("Week"),0,0);grid.addWidget(self.week,0,1);grid.addWidget(QLabel("Status"),0,2);grid.addWidget(self.status,0,3);grid.addWidget(QLabel("Availability"),1,0);grid.addWidget(self.blocks_summary,1,1);grid.addWidget(QLabel("Total Hours"),1,2);grid.addWidget(self.hours_summary,1,3);grid.addWidget(QLabel("Submission Deadline"),2,0);grid.addWidget(self.deadline_summary,2,1,1,3);root.addWidget(summary)
        self.message=QLabel();self.message.setWordWrap(True);self.message.setMinimumHeight(42);root.addWidget(self.message);actions=QHBoxLayout();self.add=QPushButton("+ Add Availability");self.edit=QPushButton("Edit");self.delete=QPushButton("Delete");self.submit=QPushButton("Submit Week for Planning");[actions.addWidget(x) for x in (self.add,self.edit,self.delete)];actions.addStretch();actions.addWidget(self.submit);root.addLayout(actions)
        self.table=QTableWidget(0,6);self.table.setHorizontalHeaderLabels(["Date","From","To","Hours","Work Type","Notes"]);self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows);self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers);self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection);self.table.verticalHeader().setVisible(False);header=self.table.horizontalHeader();[header.setSectionResizeMode(c,QHeaderView.ResizeMode.ResizeToContents) for c in range(5)];header.setSectionResizeMode(5,QHeaderView.ResizeMode.Stretch);root.addWidget(self.table,1)
        self.add.clicked.connect(self._add);self.edit.clicked.connect(self._edit);self.delete.clicked.connect(self._delete);self.submit.clicked.connect(self._submit_week);self.table.itemSelectionChanged.connect(self._update_actions);self.set_editable(self.editable)
    def _range(self):
        start=self.service.next_week();return start,start+timedelta(days=6)
    def set_editable(self,enabled):self.editable=bool(enabled);self._update_actions()
    def _is_draft(self):return self.registration is None or self.registration.status==EmployeeWorkRegistration.STATUS_DRAFT
    def _selected(self):
        row=self.table.currentRow()
        if row<0 or not self.registration:return None
        bid=self.table.item(row,0).data(Qt.ItemDataRole.UserRole);return next((b for b in self.registration.blocks if b.id==bid),None)
    def _update_actions(self):
        can=self.editable and self._is_draft();selected=self._selected() is not None;self.add.setEnabled(can);self.edit.setEnabled(can and selected);self.delete.setEnabled(can and selected);self.submit.setEnabled(can and bool(self.registration and self.registration.blocks))
    def refresh(self):
        try:
            start,end=self._range();self.week.setText(f"{start:%d/%m/%Y} – {end:%d/%m/%Y} • Next week");self.registration=self.service.list_for_employee(self.employee.id,start);status=self.registration.status if self.registration else EmployeeWorkRegistration.STATUS_DRAFT;self.status.setText(status);self.table.setRowCount(0);minutes=0
            if self.registration:
                for b in sorted(self.registration.blocks,key=lambda x:(x.work_date,x.start_time)):
                    row=self.table.rowCount();self.table.insertRow(row);m=(b.end_time.hour*60+b.end_time.minute)-(b.start_time.hour*60+b.start_time.minute);minutes+=m
                    for c,v in enumerate([b.work_date.strftime("%d/%m/%Y"),b.start_time.strftime("%H:%M"),b.end_time.strftime("%H:%M"),f"{m/60:.2f}",b.work_type,b.notes or ""]):self.table.setItem(row,c,QTableWidgetItem(v))
                    self.table.item(row,0).setData(Qt.ItemDataRole.UserRole,b.id)
            count=len(self.registration.blocks) if self.registration else 0;self.blocks_summary.setText(f"{count} block{'s' if count!=1 else ''}");self.hours_summary.setText(f"{minutes/60:.2f} hours");period=self.service.get_period(start);self.deadline_summary.setText(period.submission_deadline.strftime("%d/%m/%Y") if period.submission_deadline else "Not set");self.message.setText({"DRAFT":"Draft: you can edit this week's availability before submitting.","SUBMITTED":"Submitted for manager review. This week is read-only until reopened.","ACCEPTED":"Accepted by manager. This week's registration is locked."}.get(status,""));self._update_actions()
        except Exception as exc:self.registration=None;self.message.setText(f"Could not load your work registration. {exc}");logger.exception("weekly registration refresh failed");self._update_actions()
    def _mutate(self,fn,title):
        try:fn()
        except Exception as exc:QMessageBox.warning(self,title,str(exc))
        finally:self.refresh()
    def _add(self):
        start,end=self._range();dlg=WorkRegistrationDialog(self,default_date=start,min_date=start,max_date=end)
        if dlg.exec():self._mutate(lambda:self.service.create(self.employee.id,*dlg.values(),week_start=start),"Work Registration")
    def _edit(self):
        b=self._selected()
        if not b:return
        start,end=self._range();dlg=WorkRegistrationDialog(self,b,min_date=start,max_date=end)
        if dlg.exec():
            v=dlg.values();self._mutate(lambda:self.service.update(b.id,work_date=v[0],start_time=v[1],end_time=v[2],work_type=v[3],notes=v[4]),"Work Registration")
    def _delete(self):
        b=self._selected()
        if b and QMessageBox.question(self,"Delete availability","Delete selected availability block?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self._mutate(lambda:self.service.delete(b.id),"Work Registration")
    def _submit_week(self):
        start,end=self._range()
        if self.registration and QMessageBox.question(self,"Submit availability",f"Submit availability for {start:%d/%m/%Y} – {end:%d/%m/%Y}?",QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No)==QMessageBox.StandardButton.Yes:self._mutate(lambda:self.service.submit_week(self.employee.id,start),"Submit Availability")
