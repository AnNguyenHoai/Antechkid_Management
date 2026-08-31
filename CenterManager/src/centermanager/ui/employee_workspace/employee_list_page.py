from __future__ import annotations

import logging

from PySide6.QtCore import QDate, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from centermanager.models.employee import Employee
from centermanager.ui.shared import DataTable

logger = logging.getLogger(__name__)


class EmployeeForm(QDialog):
    """Create/edit dialog for an employee profile."""

    def __init__(self, service, parent=None, employee=None):
        super().__init__(parent)
        self.s = service
        self.employee = employee

        self.setWindowTitle("Add Employee" if employee is None else "Employee Profile")
        self.setMinimumSize(760, 580)
        self.resize(820, 650)

        self._setup_ui()
        if employee is not None:
            self._load_employee(employee)

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        basic_group = QGroupBox("Basic Information")
        basic_form = QFormLayout(basic_group)
        basic_form.setLabelAlignment(Qt.AlignRight)
        basic_form.setHorizontalSpacing(18)
        basic_form.setVerticalSpacing(12)

        self.name = QLineEdit()
        self.name.setPlaceholderText("Enter employee full name")
        self.name.setMinimumHeight(36)

        self.phone = QLineEdit()
        self.phone.setPlaceholderText("Phone number")
        self.phone.setMinimumHeight(36)

        self.email = QLineEdit()
        self.email.setPlaceholderText("Email address")
        self.email.setMinimumHeight(36)

        self.address = QTextEdit()
        self.address.setPlaceholderText("Address")
        self.address.setMinimumHeight(72)

        basic_form.addRow("Full Name *", self.name)
        basic_form.addRow("Phone", self.phone)
        basic_form.addRow("Email", self.email)
        basic_form.addRow("Address", self.address)

        employment_group = QGroupBox("Employment Information")
        employment_form = QFormLayout(employment_group)
        employment_form.setLabelAlignment(Qt.AlignRight)
        employment_form.setHorizontalSpacing(18)
        employment_form.setVerticalSpacing(12)

        self.department = QLineEdit()
        self.department.setPlaceholderText("Department")
        self.department.setMinimumHeight(36)

        self.position = QLineEdit()
        self.position.setPlaceholderText("Position")
        self.position.setMinimumHeight(36)

        self.status = QComboBox()
        self.status.addItems(sorted(Employee.VALID_STATUSES))
        self.status.setMinimumHeight(36)

        self.hire = QDateEdit()
        self.hire.setCalendarPopup(True)
        self.hire.setDisplayFormat("dd/MM/yyyy")
        self.hire.setDate(QDate.currentDate())
        self.hire.setMinimumHeight(36)

        employment_form.addRow("Department", self.department)
        employment_form.addRow("Position", self.position)
        employment_form.addRow("Status", self.status)
        employment_form.addRow("Hire Date", self.hire)

        root.addWidget(basic_group)
        root.addWidget(employment_group)
        root.addStretch(1)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self.name.setFocus()

    def _load_employee(self, employee):
        self.name.setText(employee.full_name or "")
        self.phone.setText(employee.phone or "")
        self.email.setText(employee.email or "")
        self.department.setText(employee.department or "")
        self.position.setText(employee.position or "")
        self.address.setPlainText(employee.address or "")
        self.status.setCurrentText(employee.employment_status)
        if employee.hire_date:
            self.hire.setDate(
                QDate(
                    employee.hire_date.year,
                    employee.hire_date.month,
                    employee.hire_date.day,
                )
            )

    def _payload(self):
        return {
            "full_name": self.name.text(),
            "phone": self.phone.text(),
            "email": self.email.text(),
            "department": self.department.text(),
            "position": self.position.text(),
            "address": self.address.toPlainText(),
            "employment_status": self.status.currentText(),
            "hire_date": self.hire.date().toPython(),
        }

    def save(self):
        payload = self._payload()
        try:
            self.buttons.setEnabled(False)
            if self.employee is None:
                self.s.create_employee(**payload)
            else:
                self.s.update_employee(self.employee.id, **payload)
        except Exception as exc:
            logger.exception(
                "Failed to save employee profile. employee_id=%s",
                getattr(self.employee, "id", None),
            )
            QMessageBox.critical(
                self,
                "Could not save employee",
                "The employee profile could not be saved.\n\n"
                f"Reason: {exc}\n\n"
                "Please correct the information and try again. The technical details "
                "have been written to the application log.",
            )
            self.buttons.setEnabled(True)
            return

        self.accept()


class EmployeeListPage(QWidget):
    def __init__(self, service, document_service, parent=None):
        super().__init__(parent)
        self.s = service
        self.ds = document_service
        self.write_enabled = True
        self.rows = []
        self.filtered = []
        self._setup()
        self.refresh()

    def _setup(self):
        layout = QVBoxLayout(self)

        bar = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search by code, name, phone, email...")
        self.search.textChanged.connect(self.apply)

        self.filter = QComboBox()
        self.filter.addItem("All", "ALL")
        for status in sorted(Employee.VALID_STATUSES):
            self.filter.addItem(status.replace("_", " ").title(), status)
        self.filter.currentIndexChanged.connect(self.apply)

        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.refresh)

        self.upload_cv = QPushButton("Upload CV")
        self.upload_cv.clicked.connect(self.upload_selected_cv)

        self.add = QPushButton("+ Add Employee")
        self.add.clicked.connect(self.add_employee)

        for widget in (self.search, self.filter, self.refresh_btn, self.upload_cv, self.add):
            bar.addWidget(widget)
        layout.addLayout(bar)

        self.table = DataTable(
            [
                {"key": "code", "label": "Code", "sortable": True},
                {"key": "name", "label": "Name", "sortable": True},
                {"key": "position", "label": "Position", "sortable": True},
                {"key": "department", "label": "Department", "sortable": True},
                {"key": "phone", "label": "Phone", "sortable": True},
                {"key": "status", "label": "Status", "sortable": True},
                {"key": "hire_date", "label": "Hire Date", "sortable": True},
            ],
            page_size=20,
        )
        self.table.row_double_clicked.connect(self.edit_selected)
        layout.addWidget(self.table)

    def set_write_enabled(self, enabled):
        self.write_enabled = enabled
        self.add.setEnabled(enabled)
        self.upload_cv.setEnabled(enabled)

    def refresh(self):
        try:
            self.rows = self.s.list_employees()
        except Exception:
            logger.exception("Failed to load employee list")
            QMessageBox.critical(
                self,
                "Employee Workspace",
                "Could not load employee data. Technical details were written to the application log.",
            )
            self.rows = []
        self.apply()

    def apply(self):
        q = self.search.text().lower().strip()
        status = self.filter.currentData()
        data = []
        for employee in self.rows:
            if status != "ALL" and employee.employment_status != status:
                continue
            blob = " ".join(
                [
                    employee.employee_code,
                    employee.full_name,
                    employee.phone or "",
                    employee.email or "",
                    employee.position or "",
                    employee.department or "",
                ]
            ).lower()
            if q and q not in blob:
                continue
            data.append(
                {
                    "code": employee.employee_code,
                    "name": employee.full_name,
                    "position": employee.position or "-",
                    "department": employee.department or "-",
                    "phone": employee.phone or "-",
                    "status": employee.employment_status,
                    "hire_date": str(employee.hire_date or ""),
                    "_id": employee.id,
                }
            )
        self.filtered = data
        self.table.set_data(data, len(data))

    def add_employee(self):
        if not self.write_enabled:
            return
        dialog = EmployeeForm(self.s, self)
        if dialog.exec():
            self.refresh()

    def edit_selected(self, index):
        if index >= len(self.filtered):
            return
        try:
            employee = self.s.get_employee(self.filtered[index]["_id"])
        except Exception:
            logger.exception("Failed to open employee profile")
            QMessageBox.critical(self, "Employee", "Could not open the employee profile. See application log for details.")
            return
        dialog = EmployeeForm(self.s, self, employee)
        if dialog.exec():
            self.refresh()

    def upload_selected_cv(self):
        indexes = self.table.selected_rows() if hasattr(self.table, "selected_rows") else []
        if not indexes:
            QMessageBox.information(self, "Employee Documents", "Select an employee row first.")
            return
        idx = indexes[0]
        if idx >= len(self.filtered):
            return
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select CV",
            "",
            "Documents (*.pdf *.doc *.docx);;All files (*)",
        )
        if not path:
            return
        try:
            employee = self.s.get_employee(self.filtered[idx]["_id"])
            self.ds.upload(employee, path, "CV")
            QMessageBox.information(self, "Employee Documents", "CV uploaded successfully.")
        except Exception as exc:
            logger.exception("Failed to upload employee CV")
            QMessageBox.critical(
                self,
                "Employee Documents",
                f"CV upload failed.\n\nReason: {exc}\n\nTechnical details were written to the application log.",
            )
