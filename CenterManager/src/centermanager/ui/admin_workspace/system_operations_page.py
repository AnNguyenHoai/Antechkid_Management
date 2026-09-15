# -*- coding: utf-8 -*-
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,QTableWidget,QTableWidgetItem,QTextEdit,QFrame
from centermanager.ui.design_system.tokens import SPACING, TYPOGRAPHY

class SystemOperationsPage(QWidget):
    def __init__(self, service, parent=None):
        super().__init__(parent); self._service=service; self._snapshot=None; self._setup(); self.refresh()

    def _setup(self):
        layout=QVBoxLayout(self); layout.setContentsMargins(SPACING["lg"],SPACING["lg"],SPACING["lg"],SPACING["lg"]); layout.setSpacing(SPACING["md"])
        head=QHBoxLayout(); title=QLabel("🖥️ System Operations"); title.setStyleSheet(f"font-size:{TYPOGRAPHY['page_title']}px;font-weight:700;"); head.addWidget(title); head.addStretch()
        btn=QPushButton("🔄 Refresh Health"); btn.clicked.connect(self.refresh); head.addWidget(btn); layout.addLayout(head)
        self.summary=QLabel(); self.summary.setWordWrap(True); layout.addWidget(self.summary)
        self.table=QTableWidget(0,3); self.table.setHorizontalHeaderLabels(["Component","Status","Summary"]); self.table.horizontalHeader().setStretchLastSection(True); self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows); self.table.itemSelectionChanged.connect(self._show_details); layout.addWidget(self.table,1)
        self.details=QTextEdit(); self.details.setReadOnly(True); self.details.setPlaceholderText("Select a component to view details"); self.details.setMaximumHeight(180); layout.addWidget(self.details)

    def refresh(self):
        self._snapshot=self._service.snapshot(); comps=self._snapshot["components"]; self.table.setRowCount(len(comps))
        bad=0
        for r,c in enumerate(comps):
            self.table.setItem(r,0,QTableWidgetItem(c["name"])); self.table.setItem(r,1,QTableWidgetItem(c["status"])); self.table.setItem(r,2,QTableWidgetItem(c["summary"]))
            if c["status"] in ("ERROR","WARNING"): bad+=1
        stamp=self._snapshot["generated_at"].strftime("%Y-%m-%d %H:%M:%S")
        overall="HEALTHY" if not bad else ("WARNING" if all(c["status"]!="ERROR" for c in comps) else "ERROR")
        self.summary.setText(f"Overall status: <b>{overall}</b> · Checked: {stamp} · {len(comps)} components")
        self.details.clear()

    def _show_details(self):
        rows=self.table.selectionModel().selectedRows()
        if rows and self._snapshot: self.details.setPlainText(self._snapshot["components"][rows[0].row()]["details"])
