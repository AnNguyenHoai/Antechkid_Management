# -*- coding: utf-8 -*-
"""RoleFormDialog - create or edit a custom role and its permission matrix."""
from typing import Optional, Set

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QTextEdit, QScrollArea,
    QWidget, QGroupBox, QCheckBox, QHBoxLayout, QPushButton, QMessageBox,
    QLabel
)

from centermanager.services.permission_service import PermissionService, RoleLifecycleError


class RoleFormDialog(QDialog):
    def __init__(self, permission_service: PermissionService, role_id: Optional[int] = None, parent=None):
        super().__init__(parent)
        self._service = permission_service
        self._role_id = role_id
        self._is_edit = role_id is not None
        self._permission_checks: dict[str, QCheckBox] = {}
        self._role = None
        self.setWindowTitle("Edit Role" if self._is_edit else "Add Role")
        self.setMinimumWidth(620)
        self.resize(720, 650)
        self._setup_ui()
        if self._is_edit:
            self._load_role()
        else:
            self._load_permissions(set())

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()
        self.name_edit = QLineEdit(); self.name_edit.setPlaceholderText("e.g. assistant_manager")
        self.display_name_edit = QLineEdit(); self.display_name_edit.setPlaceholderText("Role name shown to users")
        self.description_edit = QTextEdit(); self.description_edit.setFixedHeight(70)
        form.addRow("Role key *", self.name_edit)
        form.addRow("Display name *", self.display_name_edit)
        form.addRow("Description", self.description_edit)
        layout.addLayout(form)

        self.system_notice = QLabel()
        self.system_notice.setWordWrap(True)
        self.system_notice.setVisible(False)
        layout.addWidget(self.system_notice)

        layout.addWidget(QLabel("Permissions"))
        self.permissions_area = QScrollArea(); self.permissions_area.setWidgetResizable(True)
        self.permissions_container = QWidget(); self.permissions_layout = QVBoxLayout(self.permissions_container)
        self.permissions_area.setWidget(self.permissions_container)
        layout.addWidget(self.permissions_area, 1)

        buttons = QHBoxLayout(); buttons.addStretch()
        self.save_btn = QPushButton("Save"); self.cancel_btn = QPushButton("Cancel")
        buttons.addWidget(self.save_btn); buttons.addWidget(self.cancel_btn); layout.addLayout(buttons)
        self.save_btn.clicked.connect(self._save); self.cancel_btn.clicked.connect(self.reject)

    def _load_role(self):
        self._role = self._service.get_role(self._role_id)
        if self._role is None:
            QMessageBox.warning(self, "Error", "Role not found."); self.reject(); return
        self.name_edit.setText(self._role.name); self.name_edit.setReadOnly(True)
        self.display_name_edit.setText(self._role.display_name)
        self.description_edit.setPlainText(self._role.description or "")
        selected = set(self._role.permission_names)
        self._load_permissions(selected)
        if self._role.is_system:
            self.system_notice.setText("This is a protected system role. Its role key and permissions cannot be changed.")
            self.system_notice.setVisible(True)
            for check in self._permission_checks.values(): check.setEnabled(False)

    def _load_permissions(self, selected: Set[str]):
        for category, permissions in self._service.get_permissions_by_category().items():
            group = QGroupBox(category.replace("_", " ").title())
            box = QVBoxLayout(group)
            for permission in permissions:
                check = QCheckBox(permission.name)
                check.setChecked(permission.name in selected)
                if permission.description: check.setToolTip(permission.description)
                self._permission_checks[permission.name] = check
                box.addWidget(check)
            self.permissions_layout.addWidget(group)
        self.permissions_layout.addStretch()

    def _save(self):
        name = self.name_edit.text().strip()
        display_name = self.display_name_edit.text().strip()
        description = self.description_edit.toPlainText().strip() or None
        permissions = {name for name, check in self._permission_checks.items() if check.isChecked()}
        if not name or not display_name:
            QMessageBox.warning(self, "Validation", "Role key and display name are required."); return
        try:
            if self._is_edit:
                self._service.update_role(self._role_id, display_name, description, permissions)
            else:
                self._service.create_role(name, display_name, description, permissions)
            self.accept()
        except (ValueError, RoleLifecycleError) as exc:
            QMessageBox.warning(self, "Role", str(exc))
        except Exception as exc:
            QMessageBox.critical(self, "Error", f"Could not save role: {exc}")
