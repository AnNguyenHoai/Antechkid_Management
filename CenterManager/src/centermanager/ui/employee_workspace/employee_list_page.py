from __future__ import annotations

import logging
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QComboBox, QDateEdit, QDialog, QDialogButtonBox, QFileDialog, QInputDialog,
    QFormLayout, QGroupBox, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidget, QListWidgetItem, QTabWidget,
    QMessageBox, QPushButton, QTextEdit, QVBoxLayout, QWidget,
)

from centermanager.models.employee import Employee
from centermanager.services.employee_service import EmployeeAccessDeniedError, EmployeeServiceError
from centermanager.services.employee_admin_management_service import (
    EmployeeAdminManagementAccessDeniedError,
    EmployeeAdminManagementService,
    EmployeeAdminManagementValidationError,
)
from centermanager.models.role import RoleDefinitions
from centermanager.core.current_user import get_current_user
from centermanager.ui.shared import DataTable

logger = logging.getLogger(__name__)


class EmployeeProfileDialog(QDialog):
    """Employee profile page.

    The class name is retained for backwards compatibility, but management
    profiles are embedded as a normal QWidget inside Employee Workspace.
    """

    profile_saved = Signal()
    back_requested = Signal()

    def __init__(
        self, service, document_service, schedule_service, working_time_service,
        employee, parent=None, self_mode=False, editable=True, embedded=False
    ):
        super().__init__(parent)
        self.s = service
        self.ds = document_service
        self.ss = schedule_service
        self.wts = working_time_service
        self.employee = employee
        self.self_mode = bool(self_mode)
        self.editable = bool(editable)
        self.embedded = bool(embedded)

        if self.embedded:
            self.setWindowFlags(Qt.WindowType.Widget)

        self.setWindowTitle("My Employee Profile" if self.self_mode else "Employee Profile")
        self.setMinimumSize(900, 620)
        self._setup_ui()
        self._load()

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(14)

        # Profile header: identity + employment summary + explicit navigation.
        header_row = QHBoxLayout()
        identity = QVBoxLayout()
        self.header = QLabel()
        self.header.setStyleSheet("font-size: 24px; font-weight: 700;")
        self.subheader = QLabel()
        self.subheader.setStyleSheet("font-size: 13px;")
        identity.addWidget(self.header)
        identity.addWidget(self.subheader)
        header_row.addLayout(identity, 1)

        self.status_badge = QLabel("ACTIVE")
        self.status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.status_badge.setMinimumWidth(90)
        self.status_badge.setStyleSheet(
            "font-weight: 700; padding: 6px 12px; border: 1px solid #b8c2cc; "
            "border-radius: 12px; background: #f4f7f9;"
        )
        header_row.addWidget(self.status_badge, 0, Qt.AlignmentFlag.AlignTop)

        if self.embedded:
            self.back_btn = QPushButton("← Employees")
            self.back_btn.clicked.connect(self.back_requested.emit)
            header_row.addWidget(self.back_btn, 0, Qt.AlignmentFlag.AlignTop)
        root.addLayout(header_row)

        self.tabs = QTabWidget()
        self.tabs.setDocumentMode(True)
        root.addWidget(self.tabs, 1)

        self._build_overview_tab()
        self._build_schedule_tab()
        self._build_working_time_tab()
        self._build_documents_tab()

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.Save | QDialogButtonBox.Cancel
        )
        self.buttons.accepted.connect(self.save)
        self.buttons.rejected.connect(self.reject)
        if not self.embedded:
            root.addWidget(self.buttons)
        else:
            # Embedded page uses the global WRITE state; keep a compact save bar.
            self.save_bar = QHBoxLayout()
            self.save_bar.addStretch()
            self.save_btn = QPushButton("Save Changes")
            self.cancel_btn = QPushButton("Reset")
            self.save_btn.clicked.connect(self.save)
            self.cancel_btn.clicked.connect(self._load)
            self.save_bar.addWidget(self.cancel_btn)
            self.save_bar.addWidget(self.save_btn)
            root.addLayout(self.save_bar)

    def _build_overview_tab(self):
        page = QWidget()
        root = QVBoxLayout(page)
        root.setContentsMargins(8, 12, 8, 8)
        root.setSpacing(14)

        personal = QGroupBox("Personal Information")
        grid = QGridLayout(personal)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(10)

        self.code = QLabel("-")
        self.name = QLineEdit()
        self.dob = QDateEdit()
        self.dob.setCalendarPopup(True)
        self.dob.setDisplayFormat("dd/MM/yyyy")
        self.gender = QLineEdit()
        self.phone = QLineEdit()
        self.email = QLineEdit()
        self.address = QTextEdit()
        self.address.setMinimumHeight(72)

        self._add_field(grid, 0, 0, "Employee Code", self.code, 1)
        self._add_field(grid, 0, 2, "Full Name", self.name, 3)
        self._add_field(grid, 1, 0, "Date of Birth", self.dob, 1)
        self._add_field(grid, 1, 2, "Gender", self.gender, 3)
        self._add_field(grid, 2, 0, "Phone", self.phone, 1)
        self._add_field(grid, 2, 2, "Email", self.email, 3)
        self._add_field(grid, 3, 0, "Address", self.address, 1)
        grid.addWidget(self.address, 3, 1, 1, 5)
        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 1)
        grid.setColumnStretch(5, 1)
        root.addWidget(personal)

        employment = QGroupBox("Employment Information")
        eg = QGridLayout(employment)
        eg.setHorizontalSpacing(18)
        eg.setVerticalSpacing(10)
        self.department = QLineEdit()
        self.position = QLineEdit()
        self.status = QComboBox()
        self.status.addItems(sorted(Employee.VALID_STATUSES))
        self.hire = QDateEdit()
        self.hire.setCalendarPopup(True)
        self.hire.setDisplayFormat("dd/MM/yyyy")

        self._add_field(eg, 0, 0, "Department", self.department, 1)
        self._add_field(eg, 0, 2, "Position", self.position, 3)
        self._add_field(eg, 1, 0, "Status", self.status, 1)
        self._add_field(eg, 1, 2, "Hire Date", self.hire, 3)
        for col in (1, 3, 5):
            eg.setColumnStretch(col, 1)
        root.addWidget(employment)

        root.addStretch()
        self.tabs.addTab(page, "Overview")

    @staticmethod
    def _add_field(grid, row, label_col, label, widget, span=1):
        label_widget = QLabel(label)
        label_widget.setStyleSheet("font-weight: 600;")
        grid.addWidget(label_widget, row, label_col, 1, 1)
        if span == 1:
            grid.addWidget(widget, row, label_col + 1, 1, 1)
        else:
            grid.addWidget(widget, row, label_col + 1, 1, span)

    def _build_schedule_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)
        title = QLabel("Expected working schedule")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        hint = QLabel("Weekly rules and date-specific exceptions.")
        hint.setStyleSheet("color: #68737d;")
        layout.addWidget(title)
        layout.addWidget(hint)
        from centermanager.ui.employee_workspace.employee_schedule_widget import EmployeeScheduleWidget
        self.schedule_widget = EmployeeScheduleWidget(
            self.ss, self.employee, editable=self.editable and not self.self_mode, parent=page
        )
        layout.addWidget(self.schedule_widget, 1)
        self.tabs.addTab(page, "Schedule")

    def _build_working_time_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)
        title = QLabel("Actual working time")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        hint = QLabel("Recorded attendance and approved working-time entries.")
        hint.setStyleSheet("color: #68737d;")
        layout.addWidget(title)
        layout.addWidget(hint)
        from centermanager.ui.employee_workspace.employee_working_time_widget import EmployeeWorkingTimeWidget
        self.working_time_widget = EmployeeWorkingTimeWidget(
            self.wts,
            self.employee,
            editable=self.editable and not self.self_mode,
            management=not self.self_mode,
            parent=page,
        )
        layout.addWidget(self.working_time_widget, 1)
        self.tabs.addTab(page, "Attendance")

    def _build_documents_tab(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(8, 12, 8, 8)

        documents = QGroupBox("Documents")
        documents_layout = QVBoxLayout(documents)
        documents_layout.setContentsMargins(12, 14, 12, 12)
        title = QLabel("Employee Documents")
        title.setStyleSheet("font-size: 16px; font-weight: 700;")
        hint = QLabel("CV and supporting documents are stored with this employee profile.")
        hint.setStyleSheet("color: #68737d;")
        documents_layout.addWidget(title)
        documents_layout.addWidget(hint)

        self.docs = QListWidget()
        self.docs.setMinimumHeight(160)
        documents_layout.addWidget(self.docs, 1)

        actions = QHBoxLayout()
        self.upload_btn = QPushButton("Upload / Replace CV")
        self.open_btn = QPushButton("Open Selected")
        actions.addWidget(self.upload_btn)
        actions.addWidget(self.open_btn)
        actions.addStretch()
        documents_layout.addLayout(actions)
        layout.addWidget(documents, 1)
        self.upload_btn.clicked.connect(self.upload_cv)
        self.open_btn.clicked.connect(self.open_selected)
        self.tabs.addTab(page, "Documents")

    def _load(self):
        e = self.employee
        self.header.setText(e.full_name or "Employee")
        self.subheader.setText(
            f"{e.employee_code or '-'}  •  {e.position or 'Position not set'}  •  "
            f"{e.department or 'Department not set'}"
        )
        self.status_badge.setText((e.employment_status or "UNKNOWN").replace("_", " "))
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
        self._apply_edit_state()
        self._load_documents()
        if hasattr(self, "schedule_widget"):
            self.schedule_widget.employee = e
            self.schedule_widget.refresh()
        if hasattr(self, "working_time_widget"):
            self.working_time_widget.employee = e
            self.working_time_widget.refresh()

    def _apply_edit_state(self):
        personal_widgets = (
            self.name, self.dob, self.gender, self.phone, self.email, self.address
        )
        employment_widgets = (
            self.department, self.position, self.status, self.hire
        )
        for widget in personal_widgets + employment_widgets:
            widget.setEnabled(self.editable)
        self.code.setEnabled(False)

        if self.self_mode:
            for widget in employment_widgets:
                widget.setEnabled(False)

        if hasattr(self, "schedule_widget"):
            self.schedule_widget.set_editable(self.editable and not self.self_mode)
        if hasattr(self, "working_time_widget"):
            self.working_time_widget.set_editable(self.editable and not self.self_mode)

        self.upload_btn.setEnabled(self.editable)
        self.open_btn.setEnabled(self.docs.count() > 0)
        if hasattr(self, "save_btn"):
            self.save_btn.setEnabled(self.editable)
            self.cancel_btn.setEnabled(True)

    def _load_documents(self):
        self.docs.clear()
        try:
            for doc in self.ds.list_documents(self.employee.id):
                item = QListWidgetItem()
                item.setText(f"📄  {doc.original_filename}\n    {doc.document_type}")
                item.setData(Qt.ItemDataRole.UserRole, doc.relative_path)
                self.docs.addItem(item)
        except Exception:
            logger.exception("Failed to load employee documents: employee_id=%s", self.employee.id)
        self.open_btn.setEnabled(self.docs.count() > 0)

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
        if not self.editable:
            return
        try:
            if hasattr(self, "buttons"):
                self.buttons.setEnabled(False)
            if hasattr(self, "save_btn"):
                self.save_btn.setEnabled(False)
            self.s.update_employee(self.employee.id, **self._payload())
            if self.embedded:
                self.profile_saved.emit()
                self._load()
            else:
                self.accept()
        except Exception as exc:
            logger.exception("Failed to save employee profile: employee_id=%s", self.employee.id)
            QMessageBox.critical(
                self, "Could not save employee",
                f"The profile could not be saved.\n\nReason: {exc}\n\nSee application log for technical details."
            )
            if hasattr(self, "buttons"):
                self.buttons.setEnabled(True)
            if hasattr(self, "save_btn"):
                self.save_btn.setEnabled(self.editable)

    def upload_cv(self):
        if not self.editable:
            return
        path, _ = QFileDialog.getOpenFileName(
            self, "Select CV", "", "Documents (*.pdf *.doc *.docx);;All files (*)"
        )
        if not path:
            return
        try:
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
            from types import SimpleNamespace
            document = SimpleNamespace(relative_path=relative_path)
            path = self.ds.resolve_document_path(document)
            if not path.is_file():
                raise FileNotFoundError(f"Document file not found: {path}")
            import os
            os.startfile(str(path))
            logger.info("Opened employee document: employee_id=%s path=%s", self.employee.id, path)
        except Exception as exc:
            logger.exception(
                "Failed to open employee document: employee_id=%s path=%s",
                self.employee.id, relative_path
            )
            QMessageBox.warning(self, "Document", f"Could not open document.\n\nReason: {exc}")


class EmployeeListPage(QWidget):
    def __init__(self, service, document_service, schedule_service, working_time_service, permission_service, parent=None):
        super().__init__(parent)
        self.s = service
        self.ds = document_service
        self.ss = schedule_service
        self.wts = working_time_service
        self.ps = permission_service
        self._admin_service = EmployeeAdminManagementService(getattr(permission_service, "_session_factory"))
        self._selected_employee_id = None
        # Global WRITE mode is OFF until MainWindow grants it.
        self.write_enabled = False
        self._profile_opener = None
        self.rows = []
        self.filtered = []
        self._setup()
        self.refresh()

    def _setup(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)

        title_row = QHBoxLayout()
        title = QLabel("Employees")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        self.count_label = QLabel("0 employees")
        self.count_label.setStyleSheet("color: #68737d;")
        title_row.addWidget(title)
        title_row.addStretch()
        title_row.addWidget(self.count_label)
        layout.addLayout(title_row)

        subtitle = QLabel("Select an employee to open the full profile.")
        subtitle.setStyleSheet("color: #68737d;")
        layout.addWidget(subtitle)

        bar = QHBoxLayout()
        self.search = QLineEdit(); self.search.setPlaceholderText("Search code, name, phone, email...")
        self.search.textChanged.connect(self.apply)
        self.filter = QComboBox(); self.filter.addItem("All", "ALL")
        for status in sorted(Employee.VALID_STATUSES):
            self.filter.addItem(status.replace("_", " ").title(), status)
        self.filter.currentIndexChanged.connect(self.apply)
        self.refresh_btn = QPushButton("Refresh"); self.refresh_btn.clicked.connect(self.refresh)
        self.delete_btn = QPushButton("Delete Employee")
        self.delete_btn.setToolTip("Delete an employee only when no operational history exists.")
        self.delete_btn.clicked.connect(self.delete_selected)
        for w in (self.search, self.filter, self.refresh_btn, self.delete_btn): bar.addWidget(w)
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
        self.table.selection_changed.connect(self._on_selection_changed)
        layout.addWidget(self.table)

    @staticmethod
    def _is_admin():
        user = get_current_user()
        return bool(user and getattr(getattr(user, "role", None), "name", None) == RoleDefinitions.ADMIN)

    def set_profile_opener(self, callback):
        self._profile_opener = callback

    def set_write_enabled(self, enabled):
        self.write_enabled = bool(enabled)
        self._update_actions()

    def _on_selection_changed(self, rows):
        self._selected_employee_id = None
        for row in rows:
            if 0 <= row < len(self.filtered):
                self._selected_employee_id = self.filtered[row].get("_id")
                break
        self._update_actions()

    def _update_actions(self):
        self.delete_btn.setEnabled(
            self.write_enabled and self._is_admin() and self._selected_employee_id is not None
        )

    def delete_selected(self):
        if not self.write_enabled or not self._is_admin():
            return
        employee_id = self._selected_employee_id
        if employee_id is None:
            return
        employee = next((e for e in self.rows if e.id == employee_id), None)
        if employee is None:
            return
        reason, accepted = QInputDialog.getText(
            self, "Delete Employee", "Reason for deleting this employee:"
        )
        if not accepted or not reason.strip():
            return
        if QMessageBox.question(
            self,
            "Confirm Employee Deletion",
            f"Delete employee {employee.employee_code} — {employee.full_name}?\n\n"
            "Employees with operational history cannot be hard-deleted and will be rejected.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self._admin_service.delete_employee(employee_id, reason=reason.strip())
            self.refresh()
            QMessageBox.information(self, "Employee", "Employee deleted successfully.")
        except (EmployeeAdminManagementAccessDeniedError, EmployeeAdminManagementValidationError) as exc:
            QMessageBox.warning(self, "Delete Employee", str(exc))
        except Exception as exc:
            logger.exception("Failed to delete employee: employee_id=%s", employee_id)
            QMessageBox.critical(self, "Delete Employee", f"Could not delete employee.\n\nReason: {exc}")

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
        self._selected_employee_id = None
        self.filtered=data; self.table.set_data(data,len(data)); self.count_label.setText("{} employee{}".format(len(data), "s" if len(data) != 1 else "")); self._update_actions()

    def edit_selected(self, index):
        if index >= len(self.filtered): return
        try:
            employee = self.s.get_employee(self.filtered[index]["_id"])
            if self._profile_opener is not None:
                self._profile_opener(employee)
                return
            dialog = EmployeeProfileDialog(
                self.s, self.ds, self.ss, self.wts, employee, self, self_mode=False,
                editable=self.write_enabled
            )
            if dialog.exec(): self.refresh()
        except Exception as exc:
            logger.exception("Failed to open employee profile")
            QMessageBox.critical(self, "Employee Profile", f"Could not open profile.\n\nReason: {exc}")

    def set_write_enabled(self, enabled):
        self.write_enabled = bool(enabled)
        self._update_actions()
