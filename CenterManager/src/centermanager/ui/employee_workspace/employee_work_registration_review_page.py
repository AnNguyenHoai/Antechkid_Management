from __future__ import annotations
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QMessageBox
from PySide6.QtCore import Qt
from centermanager.models.employee_work_registration import EmployeeWorkRegistration

class EmployeeWorkRegistrationReviewPage(QWidget):
    """Management view of employee availability used for monthly planning."""
    def __init__(self, employee_service, registration_service, parent=None):
        super().__init__(parent); self._es=employee_service; self._rs=registration_service; self._setup(); self.refresh()
    def _setup(self):
        root=QVBoxLayout(self); root.setContentsMargins(28,24,28,24); root.setSpacing(12)
        title=QLabel("Work Registrations"); title.setStyleSheet("font-size:24px;font-weight:700;"); root.addWidget(title)
        hint=QLabel("Review employee availability for the coming month before creating the official work schedule. Registration is not attendance and does not approve working time."); hint.setWordWrap(True); hint.setStyleSheet("color:#68737d;"); root.addWidget(hint)
        bar=QHBoxLayout(); self.month=QLabel(); self.month.setStyleSheet("font-size:15px;font-weight:600;"); bar.addWidget(self.month); bar.addStretch(); self.close_btn=QPushButton("Close Registration Month"); self.close_btn.setToolTip("Close submitted availability after planning is complete."); bar.addWidget(self.close_btn); self.refresh_btn=QPushButton("Refresh"); bar.addWidget(self.refresh_btn); root.addLayout(bar)
        self.table=QTableWidget(0,8); self.table.setHorizontalHeaderLabels(["Employee","Code","Date","From","To","Hours","Type","Status"]); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers); self.table.verticalHeader().setVisible(False)
        h=self.table.horizontalHeader(); h.setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch); h.setSectionResizeMode(1,QHeaderView.ResizeMode.ResizeToContents); h.setSectionResizeMode(2,QHeaderView.ResizeMode.ResizeToContents); h.setSectionResizeMode(3,QHeaderView.ResizeMode.ResizeToContents); h.setSectionResizeMode(4,QHeaderView.ResizeMode.ResizeToContents); h.setSectionResizeMode(5,QHeaderView.ResizeMode.ResizeToContents); h.setSectionResizeMode(6,QHeaderView.ResizeMode.ResizeToContents); h.setSectionResizeMode(7,QHeaderView.ResizeMode.ResizeToContents)
        root.addWidget(self.table,1); self.refresh_btn.clicked.connect(self.refresh); self.close_btn.clicked.connect(self.close_month)
    def _period(self): return self._rs.next_month()
    def refresh(self):
        try:
            y,m=self._period(); rows=self._rs.list_all(y,m); self.month.setText(f"Planning input: {m:02d}/{y}  •  Next month"); self.table.setRowCount(0)
            for r in rows:
                i=self.table.rowCount(); self.table.insertRow(i); e=r.employee; mins=(r.end_time.hour*60+r.end_time.minute)-(r.start_time.hour*60+r.start_time.minute); vals=[e.full_name or "-",e.employee_code or "-",r.work_date.strftime("%d/%m/%Y"),r.start_time.strftime("%H:%M"),r.end_time.strftime("%H:%M"),f"{mins/60:.2f}",r.work_type,r.status]
                for c,v in enumerate(vals): self.table.setItem(i,c,QTableWidgetItem(v))
            self.close_btn.setEnabled(any(r.status==EmployeeWorkRegistration.STATUS_SUBMITTED for r in rows))
        except Exception as exc: QMessageBox.warning(self,"Work Registrations",f"Could not load registrations.\n\n{exc}")
    def close_month(self):
        y,m=self._period()
        if QMessageBox.question(self,"Close registration month",f"Close submitted availability for {m:02d}/{y}?\n\nDo this only after the manager has finished using it for planning.")==QMessageBox.StandardButton.Yes:
            try:self._rs.close_month(y,m); self.refresh()
            except Exception as exc: QMessageBox.warning(self,"Work Registrations",str(exc))
