# src/centermanager/ui/admin_workspace/user_list_page.py
# -*- coding: utf-8 -*-
"""
UserListPage - Admin user management.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QMessageBox, QMenu
)
from PySide6.QtGui import QAction

from centermanager.models.user import User
from centermanager.services.permission_service import PermissionService, UserNotFoundError
from centermanager.ui.design_system import SearchBar, PrimaryButton, SecondaryButton
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget
from centermanager.ui.admin_workspace.user_form_dialog import UserFormDialog

logger = logging.getLogger(__name__)


class UserListPage(QWidget):
    user_selected = Signal(int)

    def __init__(
        self,
        permission_service: PermissionService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = permission_service
        self._users: List[User] = []
        self._filtered: List[User] = []

        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Toolbar
        toolbar = QWidget()
        toolbar.setStyleSheet(f"""
            background: {COLORS['surface']};
            padding: {SPACING['sm']}px {SPACING['md']}px;
            border-bottom: 1px solid {COLORS['border_light']};
        """)
        toolbar_layout = QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(0, 0, 0, 0)
        toolbar_layout.setSpacing(SPACING['sm'])

        self.search_bar = SearchBar("Search by username, name, email...")
        self.search_bar.text_changed.connect(self._on_search)
        toolbar_layout.addWidget(self.search_bar)

        self.refresh_btn = SecondaryButton("🔄 Refresh")
        self.refresh_btn.setFixedHeight(34)
        self.refresh_btn.clicked.connect(self.refresh)
        toolbar_layout.addWidget(self.refresh_btn)

        self.add_btn = PrimaryButton("+ Add User")
        self.add_btn.setFixedHeight(34)
        self.add_btn.clicked.connect(self._show_add_dialog)
        toolbar_layout.addWidget(self.add_btn)

        layout.addWidget(toolbar)

        # Data Table
        columns = [
            {"key": "username", "label": "Username", "sortable": True},
            {"key": "full_name", "label": "Name", "sortable": True},
            {"key": "role", "label": "Role", "sortable": True},
            {"key": "status", "label": "Status", "sortable": True},
            {"key": "last_login", "label": "Last Login", "sortable": True},
            {"key": "actions", "label": "Actions", "sortable": False},
        ]
        self.data_table = DataTable(columns, page_size=20)
        self.data_table.row_double_clicked.connect(self._on_row_double_clicked)
        self.data_table.context_menu_requested.connect(self._on_context_menu)
        layout.addWidget(self.data_table)

        self.loading = LoadingWidget()
        self.loading.setVisible(False)
        layout.addWidget(self.loading)

    def refresh(self) -> None:
        self.loading.setVisible(True)
        try:
            self._users = self._service.get_all_users()
            self._apply_filters()
        except Exception as e:
            logger.exception("Failed to refresh user list")
            QMessageBox.critical(self, "Error", "Failed to load users.")
        finally:
            self.loading.setVisible(False)

    def _apply_filters(self) -> None:
        search = self.search_bar.text().strip().lower()
        if search:
            self._filtered = [u for u in self._users if
                              search in u.username.lower() or
                              search in u.full_name.lower() or
                              (u.email and search in u.email.lower())]
        else:
            self._filtered = self._users[:]
        self._populate_table()

    def _populate_table(self) -> None:
        data = []
        for user in self._filtered:
            role_name = user.role.display_name if user.role else "No Role"
            status = "Active" if user.is_active else "Inactive"
            if user.is_locked:
                status = "Locked"
            last_login = user.last_login.strftime("%d/%m/%Y %H:%M") if user.last_login else "-"
            data.append({
                "username": user.username,
                "full_name": user.full_name,
                "role": role_name,
                "status": status,
                "last_login": last_login,
                "_id": user.id,
            })
        self.data_table.set_data(data, len(data))

    def _on_search(self, text: str) -> None:
        self._apply_filters()

    def _on_row_double_clicked(self, row: int) -> None:
        if row < len(self._filtered):
            self._show_edit_dialog(self._filtered[row].id)

    def _on_context_menu(self, pos, row: int) -> None:
        if row < 0 or row >= len(self._filtered):
            return
        user = self._filtered[row]
        menu = QMenu(self)
        edit_action = QAction("Edit", self)
        edit_action.triggered.connect(lambda: self._show_edit_dialog(user.id))
        menu.addAction(edit_action)

        reset_action = QAction("Reset Password", self)
        reset_action.triggered.connect(lambda: self._reset_password(user.id))
        menu.addAction(reset_action)

        menu.addSeparator()

        if user.is_active:
            deactivate_action = QAction("Deactivate", self)
            deactivate_action.triggered.connect(lambda: self._toggle_active(user.id, False))
            menu.addAction(deactivate_action)
        else:
            activate_action = QAction("Activate", self)
            activate_action.triggered.connect(lambda: self._toggle_active(user.id, True))
            menu.addAction(activate_action)

        if user.is_locked:
            unlock_action = QAction("Unlock", self)
            unlock_action.triggered.connect(lambda: self._unlock_user(user.id))
            menu.addAction(unlock_action)

        menu.exec(pos)

    def _show_add_dialog(self) -> None:
        dialog = UserFormDialog(self._service, parent=self)
        if dialog.exec() == UserFormDialog.DialogCode.Accepted:
            self.refresh()

    def _show_edit_dialog(self, user_id: int) -> None:
        dialog = UserFormDialog(self._service, user_id=user_id, parent=self)
        if dialog.exec() == UserFormDialog.DialogCode.Accepted:
            self.refresh()

    def _reset_password(self, user_id: int) -> None:
        reply = QMessageBox.question(
            self,
            "Reset Password",
            "Reset password for this user? They will need to change it on next login.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                new_password = self._service.reset_user_password(user_id)
                QMessageBox.information(
                    self,
                    "Password Reset",
                    f"Temporary password: {new_password}\n\nUser must change this password on next login."
                )
                self.refresh()
            except Exception as e:
                logger.exception("Reset password failed")
                QMessageBox.critical(self, "Error", str(e))

    def _toggle_active(self, user_id: int, active: bool) -> None:
        action = "Activate" if active else "Deactivate"
        reply = QMessageBox.question(
            self,
            f"{action} User",
            f"{action} this user?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if reply == QMessageBox.StandardButton.Yes:
            try:
                self._service.set_user_active(user_id, active)
                self.refresh()
            except Exception as e:
                logger.exception(f"{action} failed")
                QMessageBox.critical(self, "Error", str(e))

    def _unlock_user(self, user_id: int) -> None:
        try:
            self._service.unlock_user(user_id)
            self.refresh()
            QMessageBox.information(self, "Unlocked", "User account has been unlocked.")
        except Exception as e:
            logger.exception("Unlock failed")
            QMessageBox.critical(self, "Error", str(e))