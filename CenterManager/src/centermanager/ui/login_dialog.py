# -*- coding: utf-8 -*-
"""
LoginDialog - simple login dialog for authentication.
"""
import hashlib
import logging
import traceback
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QPushButton, QLabel, QWidget
)

from centermanager.models.user import User
from centermanager.services.permission_service import PermissionService
from centermanager.core.current_user import set_current_user

logger = logging.getLogger(__name__)


class LoginDialog(QDialog):
    login_successful = Signal(User)

    def __init__(
        self,
        permission_service: PermissionService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._permission_service = permission_service
        self._user: Optional[User] = None

        self.setWindowTitle("CenterManager - Login")
        self.setMinimumSize(350, 220)
        self.setModal(True)
        self.setWindowFlags(
            self.windowFlags() & ~Qt.WindowType.WindowContextHelpButtonHint
        )

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        header = QLabel("🏛️ CenterManager")
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        header.setStyleSheet("font-size: 24px; font-weight: bold; color: #1976d2;")
        layout.addWidget(header)

        subheader = QLabel("Please sign in to continue")
        subheader.setAlignment(Qt.AlignmentFlag.AlignCenter)
        subheader.setStyleSheet("font-size: 13px; color: #666;")
        layout.addWidget(subheader)

        layout.addSpacing(8)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("Enter username")
        self.username_edit.setFixedHeight(32)
        form.addRow("Username:", self.username_edit)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("Enter password")
        self.password_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.password_edit.setFixedHeight(32)
        form.addRow("Password:", self.password_edit)

        layout.addLayout(form)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #d32f2f; font-size: 12px;")
        self.error_label.setVisible(False)
        layout.addWidget(self.error_label)

        layout.addSpacing(8)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.login_btn = QPushButton("Sign In")
        self.login_btn.setFixedWidth(100)
        self.login_btn.setDefault(True)

        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)

        btn_layout.addWidget(self.login_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.username_edit.setFocus()

    def _connect_signals(self) -> None:
        self.login_btn.clicked.connect(self._login)
        self.cancel_btn.clicked.connect(self.reject)
        self.username_edit.returnPressed.connect(self.password_edit.setFocus)
        self.password_edit.returnPressed.connect(self._login)

    def _login(self) -> None:
        username = self.username_edit.text().strip()
        password = self.password_edit.text()

        if not username:
            self._show_error("Please enter username.")
            self.username_edit.setFocus()
            return

        if not password:
            self._show_error("Please enter password.")
            self.password_edit.setFocus()
            return

        try:
            password_hash = hashlib.sha256(password.encode()).hexdigest()
        except Exception as e:
            logger.exception("Hashing error")
            self._show_error("Internal error during login.")
            return

        try:
            logger.info(f"Attempting login for user: {username}")
            user = self._permission_service.get_user_by_username(username)
            if user is None:
                self._show_error("Invalid username or password.")
                return

            if not user.is_active:
                self._show_error("Account is deactivated.")
                return

            if user.password_hash != password_hash:
                self._show_error("Invalid username or password.")
                return

            # Login successful
            self._user = user
            set_current_user(user)
            logger.info(f"User logged in: {username} (role: {user.role.name if user.role else 'none'})")
            
            self.error_label.setVisible(False)
            self.login_successful.emit(user)
            self.accept()

        except Exception as e:
            logger.exception(f"Login error for user {username}: {e}")
            # Log stack trace to file
            logger.error(traceback.format_exc())
            self._show_error(f"Login error: {str(e)}")

    def _show_error(self, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.setVisible(True)

    def get_user(self) -> Optional[User]:
        return self._user