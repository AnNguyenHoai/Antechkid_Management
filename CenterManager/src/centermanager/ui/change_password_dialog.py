# -*- coding: utf-8 -*-
"""
ChangePasswordDialog - Force user to change password on first login.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QMessageBox, QWidget
)

from centermanager.models.user import User
from centermanager.services.permission_service import PermissionService, AuthenticationError

logger = logging.getLogger(__name__)


class ChangePasswordDialog(QDialog):
    password_changed = Signal(User)

    def __init__(
        self,
        user: User,
        permission_service: PermissionService
    ) -> None:
        super().__init__()
        self._user = user
        self._permission_service = permission_service

        self.setWindowTitle("Change Password")
        self.setMinimumWidth(400)
        self.setModal(True)

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        msg = QLabel("You are required to change your password before continuing.")
        msg.setWordWrap(True)
        msg.setStyleSheet("font-size: 14px; color: #333;")
        layout.addWidget(msg)

        layout.addSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.current_password_edit = QLineEdit()
        self.current_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.current_password_edit.setPlaceholderText("Enter current password")
        form.addRow("Current Password:", self.current_password_edit)

        self.new_password_edit = QLineEdit()
        self.new_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.new_password_edit.setPlaceholderText("Enter new password (min 6 characters)")
        form.addRow("New Password:", self.new_password_edit)

        self.confirm_password_edit = QLineEdit()
        self.confirm_password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.confirm_password_edit.setPlaceholderText("Confirm new password")
        form.addRow("Confirm Password:", self.confirm_password_edit)

        layout.addLayout(form)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #d32f2f; font-size: 12px;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Change Password")
        self.save_btn.setFixedWidth(140)
        self.save_btn.setDefault(True)
        btn_layout.addWidget(self.save_btn)
        layout.addLayout(btn_layout)

    def _connect_signals(self) -> None:
        self.save_btn.clicked.connect(self._change_password)
        self.new_password_edit.returnPressed.connect(self.save_btn.click)
        self.confirm_password_edit.returnPressed.connect(self.save_btn.click)

    def _change_password(self) -> None:
        current = self.current_password_edit.text()
        new_password = self.new_password_edit.text()
        confirm = self.confirm_password_edit.text()

        if len(new_password) < 6:
            self._show_error("New password must be at least 6 characters.")
            return

        if new_password != confirm:
            self._show_error("Passwords do not match.")
            return

        if new_password == current:
            self._show_error("New password must be different from current password.")
            return

        try:
            updated_user = self._permission_service.change_password(
                self._user.id,
                current,
                new_password,
            )

            self._user = updated_user
            logger.info(f"Password changed for user {updated_user.username}")
            self.password_changed.emit(updated_user)
            self.accept()

        except AuthenticationError as e:
            self._show_error(str(e))
        except Exception as e:
            logger.exception("Error changing password")
            QMessageBox.critical(self, "Error", f"Could not change password: {str(e)}")

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)
        self.current_password_edit.setFocus()
