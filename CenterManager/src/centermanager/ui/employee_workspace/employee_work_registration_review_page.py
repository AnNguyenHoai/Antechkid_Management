from __future__ import annotations
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox
from PySide6.QtCore import Qt
from centermanager.models.employee_work_registration import EmployeeWorkRegistration

class EmployeeWorkRegistrationReviewPage(QWidget):
    """Manager view: one row per employee/month, with aggregate actions."""
    def __init__(self,employee_service,registration_service,parent=None):
        super().__init__(parent); self._es=employee_service; self._rs=registration_service; self._rows=[]; self._setup(); self.refresh()
    def _setup(self):
        root=QVBoxLayout(self); root.setContentsMargins(28,24,28,24); root.setSpacing(12)
        title=QLabel("Work Registrations"); title.setStyleSheet("font-size:24px;font-weight:700;"); root.addWidget(title)
        hint=QLabel("Each employee has one monthly registration containing all availability blocks. Review and accept registrations before building the official schedule."); hint.setWordWrap(True); hint.setStyleSheet("color:#68737d;"); root.addWidget(hint)
        bar=QHBoxLayout(); self.month=QLabel(); self.month.setStyleSheet("font-size:15px;font-weight:600;"); bar.addWidget(self.month); bar.addStretch(); self.accept_btn=QPushButton("Accept Selected"); self.reopen_btn=QPushButton("Reopen Selected"); self.close_btn=QPushButton("Close Registration Month"); self.refresh_btn=QPushButton("Refresh")
        for b in (self.accept_btn,self.reopen_btn,self.close_btn,self.refresh_btn):bar.addWidget(b)
        root.addLayout(bar)
        self.table=QTableWidget(0,7); self.table.setHorizontalHeaderLabels(["Employee","Code","Blocks","Total Hours","Status","Submitted","Accepted"]); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.verticalHeader().setVisible(False); h=self.table.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch); [h.setSectionResizeMode(c,QHeaderView.ResizeMode.ResizeToContents) for c in range(1,7)]; root.addWidget(self.table,1)
        self.refresh_btn.clicked.connect(self.refresh); self.accept_btn.clicked.connect(self.accept_selected); self.reopen_btn.clicked.connect(self.reopen_selected); self.close_btn.clicked.connect(self.close_month); self.table.itemSelectionChanged.connect(self._update_actions)
    def _period(self):return self._rs.next_month()
    def refresh(self):
        try:
            y,m=self._period(); self.month.setText(f"Planning input: {m:02d}/{y} • Next month"); self._rows=self._rs.list_all(y,m); self.table.setRowCount(0)
            for r in self._rows:
                hours=sum((b.end_time.hour*60+b.end_time.minute)-(b.start_time.hour*60+b.start_time.minute) for b in r.blocks)/60
                vals=[r.employee.full_name or "-",r.employee.employee_code or "-",str(len(r.blocks)),f"{hours:.2f}",r.status,r.submitted_at.strftime("%d/%m/%Y %H:%M") if r.submitted_at else "-",r.accepted_at.strftime("%d/%m/%Y %H:%M") if r.accepted_at else "-"]
                i=self.table.rowCount(); self.table.insertRow(i)
                for c,v in enumerate(vals):self.table.setItem(i,c,QTableWidgetItem(v))
                self.table.item(i,0).setData(Qt.ItemDataRole.UserRole,r.employee_id)
            self._update_actions()
        except Exception as exc:QMessageBox.warning(self,"Work Registrations",f"Could not load registrations.\n\n{exc}")
    def _selected(self):
        i=self.table.currentRow(); return self._rows[i] if 0<=i<len(self._rows) else None
    def _update_actions(self):
        r=self._selected(); all_accepted=bool(self._rows) and all(x.status==EmployeeWorkRegistration.STATUS_ACCEPTED for x in self._rows); self.accept_btn.setEnabled(bool(r and r.status==EmployeeWorkRegistration.STATUS_SUBMITTED)); self.reopen_btn.setEnabled(bool(r and r.status==EmployeeWorkRegistration.STATUS_ACCEPTED)); self.close_btn.setEnabled(all_accepted)
    def accept_selected(self):
        r=self._selected();
        if not r:return
        y,m=self._period()
        try:self._rs.accept(r.employee_id,y,m);self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Accept Registration",str(exc))
    def reopen_selected(self):
        r=self._selected();
        if not r:return
        y,m=self._period()
        try:self._rs.reopen(r.employee_id,y,m);self.refresh()
        except Exception as exc:QMessageBox.warning(self,"Reopen Registration",str(exc))
    def close_month(self):
        y,m=self._period()
        if QMessageBox.question(self,"Close registration month",f"Close the {m:02d}/{y} registration period after all registrations are accepted?")==QMessageBox.StandardButton.Yes:
            try:self._rs.close_month(y,m);self.refresh()
            except Exception as exc:QMessageBox.warning(self,"Close Registration",str(exc))
