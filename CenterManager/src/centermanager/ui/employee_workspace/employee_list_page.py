from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from centermanager.models.employee import Employee
from centermanager.services.employee_service import EmployeeAccessDeniedError, EmployeeServiceError
from centermanager.ui.shared import DataTable

logger = logging.getLogger(__name__)


class EmployeeProfileDialog(QDialog):
    """Full employee profile editor. CV/documents are managed inside the profile."""

    def __init__(self, service, document_service, employee, parent=None, self_mode=False, editable=True):
        super().__init__(parent)
        self.s = service
        self.ds = document_service
        self.employee = employee
        self.self_mode = self_mode
        self.editable = editable
        self.setWindowTitle("My Employee Profile" if self_mode else "Employee Profile")
        self.setMinimumSize(820, 700)
        self.resize(900, 760)
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        header = QLabel()
        header.setStyleSheet("font-size: 22px; font-weight: 700;")
        self.header = header
        root.addWidget(header)

        basic = QGroupBox("Personal Information")
        form = QFormLayout(basic)
        form.setVerticalSpacing(10)
        self.code = QLabel("-")
        self.name = QLineEdit()
        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True); self.dob.setDisplayFormat("dd/MM/yyyy")
        self.gender = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.address = QTextEdit(); self.address.setMinimumHeight(70)
        for w in (self.name, self.gender, self.phone, self.email): w.setMinimumHeight(34)
        form.addRow("Employee Code", self.code)
        form.addRow("Full Name", self.name)
        form.addRow("Date of Birth", self.dob)
        form.addRow("Gender", self.gender)
        form.addRow("Phone", self.phone)
        form.addRow("Email", self.email)
        form.addRow("Address", self.address)
        root.addWidget(basic)

        employment = QGroupBox("Employment Information")
        ef = QFormLayout(employment)
        self.department = QLineEdit(); self.position = QLineEdit()
        self.status = QComboBox(); self.status.addItems(sorted(Employee.VALID_STATUSES))
        self.hire = QDateEdit(); self.hire.setCalendarPopup(True); self.hire.setDisplayFormat("dd/MM/yyyy")
        for w in (self.department, self.position, self.status, self.hire): w.setMinimumHeight(34)
        ef.addRow("Department", self.department)
        ef.addRow("Position", self.position)
        ef.addRow("Status", self.status)
        ef.addRow("Hire Date", self.hire)
        root.addWidget(employment)

        docs = QGroupBox("Documents")
        dl = QVBoxLayout(docs)
        self.docs = QListWidget()
        self.docs.setMinimumHeight(100)
        dl.addWidget(self.docs)
        db = QHBoxLayout()
        self.upload_btn = QPushButton("Upload / Replace CV")
        self.open_btn = QPushButton("Open Selected")
        db.addWidget(self.upload_btn); db.addWidget(self.open_btn); db.addStretch()
        dl.addLayout(db)
        root.addWidget(docs)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.upload_btn.clicked.connect(self.upload_cv)
        self.open_btn.clicked.connect(self.open_selected)

        if self.self_mode:
            # Self-service may edit personal information only.
            for w in (self.department, self.position, self.status, self.hire):
                w.setEnabled(False)
            self.code.setEnabled(False)
        if not self.editable:
            for w in (self.name, self.dob, self.gender, self.phone, self.email,
                      self.address, self.department, self.position, self.status, self.hire):
                w.setEnabled(False)
            self.buttons.button(QDialogButtonBox.StandardButton.Save).setEnabled(False)
            self.upload_btn.setEnabled(False)

    def _load(self):
        e = self.employee
        self.header.setText(f"{e.full_name or 'Employee'}  •  {e.employee_code}")
        self.code.setText(e.employee_code or "-")
        self.name.setText(e.full_name or "")
        if e.date_of_birth:
            self.dob.setDate(QDate(e.date_of_birth.year, e.date_of_birth.month, e.date_of_birth.day))
        else:
            self.dob.setDate(QDate(2000, 1, 1))
        self.gender.setText(e.gender or "")
        self.phone.setText(e.phone or "")
        self.email.setText(e.email or "")
        self.address.setPlainText(e.address or "")
        self.department.setText(e.department or "")
        self.position.setText(e.position or "")
        self.status.setCurrentText(e.employment_status or Employee.STATUS_ACTIVE)
        if e.hire_date:
            self.hire.setDate(QDate(e.hire_date.year, e.hire_date.month, e.hire_date.day))
        else:
            self.hire.setDate(QDate.currentDate())
        self._load_documents()

    def _load_documents(self):
        self.docs.clear()
        try:
            for doc in self.ds.list_documents(self.employee.id):
                self.docs.addItem(f"{doc.document_type}  |  {doc.original_filename}")
                self.docs.item(self.docs.count()-1).setData(Qt.ItemDataRole.UserRole, doc.relative_path)
        except Exception:
            logger.exception("Failed to load employee documents: employee_id=%s", self.employee.id)

    def _payload(self):
        data = {
            "full_name": self.name.text().strip(),
            "date_of_birth": self.dob.date().toPython(),
            "gender": self.gender.text().strip(),
            "phone": self.phone.text().strip(),
            "email": self.email.text().strip(),
            "address": self.address.toPlainText().strip(),
        }
        if not self.self_mode:
            data.update({
                "department": self.department.text().strip(),
                "position": self.position.text().strip(),
                "employment_status": self.status.currentText(),
                "hire_date": self.hire.date().toPython(),
            })
        return data

    def save(self):
        try:
            self.buttons.setEnabled(False)
            self.s.update_employee(self.employee.id, **self._payload())
            self.accept()
        except Exception as exc:
            logger.exception("Failed to save employee profile: employee_id=%s", self.employee.id)
            QMessageBox.critical(
                self, "Could not save employee",
                f"The profile could not be saved.\n\nReason: {exc}\n\nSee application log for technical details."
            )
            self.buttons.setEnabled(True)

    def upload_cv(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CV", "", "Documents (*.pdf *.doc *.docx);;All files (*)"
        )
        if not path:
            return
        try:
            # The service receives the resolved Employee object; ownership is already
            # enforced when this profile was opened. Management profiles may manage
            # documents for the selected employee.
            self.ds.upload(self.employee, path, "CV")
            self._load_documents()
        except Exception as exc:
            logger.exception("Failed to upload employee CV: employee_id=%s", self.employee.id)
            QMessageBox.critical(self, "CV upload failed", f"Could not upload CV.\n\nReason: {exc}")

    def open_selected(self):
        item = self.docs.currentItem()
        if not item:
            return
        relative_path = item.data(Qt.ItemDataRole.UserRole)
        try:
            # Resolve relative_path through the document service. Never pass the
            # stored runtime-relative path directly to os.startfile(), because
            # Windows resolves relative paths from the process working directory.
            from types import SimpleNamespace
            document = SimpleNamespace(relative_path=relative_path)
            path = self.ds.resolve_document_path(document)
            if not path.is_file():
                raise FileNotFoundError(f"Document file not found: {path}")
            import os
            os.startfile(str(path))
            logger.info("Opened employee document: employee_id=%s path=%s", self.employee.id, path)
        except Exception as exc:
            logger.exception("Failed to open employee document: employee_id=%s path=%s", self.employee.id, relative_path)
            QMessageBox.warning(self, "Document", f"Could not open document.\n\nReason: {exc}")


class EmployeeListPage(QWidget):
    def __init__(self, service, document_service, permission_service, parent=None):
        super().__init__(parent)
        self.s = service
        self.ds = document_service
        self.ps = permission_service
        # Global WRITE mode is OFF until MainWindow grants it.
        self.write_enabled = False
        self.rows = []
        self.filtered = []
        self._setup()
        self.refresh()

    def _setup(self):
        layout = QVBoxLayout(self)
        bar = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Search by code, name, phone, email...")
        self.search.textChanged.connect(self.apply)
        self.filter = QComboBox(); self.filter.addItem("All", "ALL")
        for status in sorted(Employee.VALID_STATUSES):
            self.filter.addItem(status.replace("_", " ").title(), status)
        self.filter.currentIndexChanged.connect(self.apply)
        self.refresh_btn = QPushButton("Refresh"); self.refresh_btn.clicked.connect(self.refresh)
        for w in (self.search, self.filter, self.refresh_btn): bar.addWidget(w)
        layout.addLayout(bar)

        self.table = DataTable([
            {"key":"code","label":"Code","sortable":True},
            {"key":"name","label":"Name","sortable":True},
            {"key":"position","label":"Position","sortable":True},
            {"key":"department","label":"Department","sortable":True},
            {"key":"phone","label":"Phone","sortable":True},
            {"key":"status","label":"Status","sortable":True},
            {"key":"hire_date","label":"Hire Date","sortable":True},
            {"key":"account","label":"Account","sortable":True},
        ], page_size=20)
        self.table.row_double_clicked.connect(self.edit_selected)
        layout.addWidget(self.table)

    def set_write_enabled(self, enabled):
        self.write_enabled = enabled

    def refresh(self):
        try:
            self.rows = self.s.list_visible_employees()
        except Exception:
            logger.exception("Failed to load employee list")
            QMessageBox.critical(self, "Employee Workspace", "Could not load employee data. See application log.")
            self.rows = []
        self.apply()

    def apply(self):
        q = self.search.text().lower().strip(); status = self.filter.currentData()
        data = []
        for e in self.rows:
            if status != "ALL" and e.employment_status != status: continue
            blob = " ".join([e.employee_code,e.full_name,e.phone or "",e.email or "",e.position or "",e.department or ""]).lower()
            if q and q not in blob: continue
            data.append({"code":e.employee_code,"name":e.full_name,"position":e.position or "-",
                         "department":e.department or "-","phone":e.phone or "-","status":e.employment_status,
                         "hire_date":str(e.hire_date or ""), "account":e.user.username if e.user else "NOT LINKED",
                         "_id":e.id})
        self.filtered=data; self.table.set_data(data,len(data))

    def edit_selected(self, index):
        if index >= len(self.filtered): return
        try:
            employee = self.s.get_employee(self.filtered[index]["_id"])
            dialog = EmployeeProfileDialog(
                self.s, self.ds, employee, self, self_mode=False,
                editable=self.write_enabled
            )
            if dialog.exec(): self.refresh()
        except Exception as exc:
            logger.exception("Failed to open employee profile")
            QMessageBox.critical(self, "Employee Profile", f"Could not open profile.\n\nReason: {exc}")

    def set_write_enabled(self, enabled):
        self.write_enabled = bool(enabled)
