# src/centermanager/ui/admin_workspace/user_form_dialog.py
# -*- coding: utf-8 -*-
"""
UserFormDialog - Create or edit user.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QComboBox,
    QPushButton, QHBoxLayout, QMessageBox, QLabel, QWidget
)

from centermanager.models.role import RoleDefinitions
from centermanager.services.permission_service import PermissionService

logger = logging.getLogger(__name__)


class UserFormDialog(QDialog):
    def __init__(
        self,
        permission_service: PermissionService,
        user_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = permission_service
        self._user_id = user_id
        self._is_edit = user_id is not None

        self.setWindowTitle("Edit User" if self._is_edit else "Add User")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._setup_ui()
        if self._is_edit:
            self._load_user()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Username
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Unique username")
        if self._is_edit:
            self.username_edit.setReadOnly(True)
        form.addRow("Username *", self.username_edit)

        # Full Name
        self.full_name_edit = QLineEdit()
        self.full_name_edit.setPlaceholderText("Display name")
        form.addRow("Full Name *", self.full_name_edit)

        # Email
        self.email_edit = QLineEdit()
        self.email_edit.setPlaceholderText("Email (optional)")
        form.addRow("Email", self.email_edit)

        # Phone
        self.phone_edit = QLineEdit()
        self.phone_edit.setPlaceholderText("Phone (optional)")
        form.addRow("Phone", self.phone_edit)

        # Role
        self.role_combo = QComboBox()
        roles = [
            (RoleDefinitions.ADMIN, "Administrator"),
            (RoleDefinitions.TEACHER, "Teacher"),
            (RoleDefinitions.RECEPTION, "Reception"),
            (RoleDefinitions.FINANCE, "Finance"),
            (RoleDefinitions.MANAGER, "Manager"),
        ]
        for name, display in roles:
            self.role_combo.addItem(display, name)
        form.addRow("Role *", self.role_combo)

        # For new user, show temporary password field
        self.temp_password_edit = QLineEdit()
        self.temp_password_edit.setPlaceholderText("Leave blank to auto-generate")
        self.temp_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        if self._is_edit:
            self.temp_password_edit.setVisible(False)
        else:
            form.addRow("Temporary Password", self.temp_password_edit)

        layout.addLayout(form)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedWidth(100)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _load_user(self) -> None:
        try:
            user = self._service.get_user(self._user_id)
            if user is None:
                QMessageBox.warning(self, "Error", "User not found.")
                self.reject()
                return
            self.username_edit.setText(user.username)
            self.full_name_edit.setText(user.full_name)
            self.email_edit.setText(user.email or "")
            self.phone_edit.setText(user.phone or "")
            if user.role:
                idx = self.role_combo.findData(user.role.name)
                if idx >= 0:
                    self.role_combo.setCurrentIndex(idx)
        except Exception as e:
            logger.exception("Error loading user")
            QMessageBox.critical(self, "Error", "Could not load user data.")
            self.reject()

    def _save(self) -> None:
        username = self.username_edit.text().strip()
        full_name = self.full_name_edit.text().strip()
        email = self.email_edit.text().strip() or None
        phone = self.phone_edit.text().strip() or None
        role_name = self.role_combo.currentData()

        if not username:
            QMessageBox.warning(self, "Validation", "Username is required.")
            return
        if not full_name:
            QMessageBox.warning(self, "Validation", "Full name is required.")
            return
        if not role_name:
            QMessageBox.warning(self, "Validation", "Role is required.")
            return

        try:
            if self._is_edit:
                self._service.update_user(
                    user_id=self._user_id,
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    role_name=role_name
                )
                QMessageBox.information(self, "Success", "User updated successfully.")
            else:
                temp_password = self.temp_password_edit.text().strip() or None
                user = self._service.create_user_with_temp_password(
                    username=username,
                    full_name=full_name,
                    email=email,
                    phone=phone,
                    role_name=role_name,
                    temp_password=temp_password,
                )
                if temp_password is None:
                    # Auto-generated password, show it
                    QMessageBox.information(
                        self,
                        "User Created",
                        f"User {username} created with temporary password: {user.password_hash[:8]}...\n"
                        "Please provide this to the user."
                    )
                else:
                    QMessageBox.information(self, "User Created", f"User {username} created successfully.")
            self.accept()
        except ValueError as e:
            QMessageBox.warning(self, "Validation", str(e))
        except Exception as e:
            logger.exception("Error saving user")
            QMessageBox.critical(self, "Error", f"An unexpected error occurred: {str(e)}")