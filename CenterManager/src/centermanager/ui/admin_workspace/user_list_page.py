# -*- coding: utf-8 -*-
"""
UserListPage - Admin user management.
Now with collaboration support.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QFrame, QMessageBox, QMenu, QComboBox
)
from PySide6.QtGui import QAction

from centermanager.models.user import User
from centermanager.services.permission_service import PermissionService, UserNotFoundError, UserLifecycleError
from centermanager.ui.design_system import SearchBar, PrimaryButton, SecondaryButton
from centermanager.ui.design_system.tokens import COLORS, SPACING
from centermanager.ui.shared import DataTable, LoadingWidget
from centermanager.ui.admin_workspace.user_form_dialog import UserFormDialog
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService
from centermanager.ui.admin_workspace.access import can_write, notify
from centermanager.models.permission import PermissionDefinitions

logger = logging.getLogger(__name__)


class UserListPage(QWidget):
    user_selected = Signal(int)

    def __init__(
        self,
        permission_service: PermissionService,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = permission_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._write_enabled = can_write(self._collaboration_manager)
        self._users: List[User] = []
        self._filtered: List[User] = []
        self._roles = []

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

        self.role_filter = QComboBox()
        self.role_filter.addItem("All roles", None)
        self.role_filter.currentIndexChanged.connect(self._apply_filters)
        toolbar_layout.addWidget(self.role_filter)

        self.status_filter = QComboBox()
        self.status_filter.addItem("All statuses", None)
        self.status_filter.addItem("Active", "active")
        self.status_filter.addItem("Inactive", "inactive")
        self.status_filter.addItem("Locked", "locked")
        self.status_filter.currentIndexChanged.connect(self._apply_filters)
        toolbar_layout.addWidget(self.status_filter)

        self.password_filter = QComboBox()
        self.password_filter.addItem("Password: all", None)
        self.password_filter.addItem("Change required", True)
        self.password_filter.addItem("No change required", False)
        self.password_filter.currentIndexChanged.connect(self._apply_filters)
        toolbar_layout.addWidget(self.password_filter)

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
            {"key": "security", "label": "Security", "sortable": True},
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
            roles = self._service.get_all_roles()
            current_role = self.role_filter.currentData()
            self.role_filter.blockSignals(True)
            self.role_filter.clear(); self.role_filter.addItem("All roles", None)
            for role in roles: self.role_filter.addItem(role.display_name, role.id)
            idx = self.role_filter.findData(current_role)
            self.role_filter.setCurrentIndex(max(0, idx)); self.role_filter.blockSignals(False)
            self._apply_filters()
        except Exception as e:
            logger.exception("Failed to refresh user list")
            QMessageBox.critical(self, "Error", "Failed to load users.")
        finally:
            self.loading.setVisible(False)

    def _apply_filters(self, *_args) -> None:
        search = self.search_bar.text().strip().lower()
        role_id = self.role_filter.currentData()
        status = self.status_filter.currentData()
        password_change = self.password_filter.currentData()
        filtered = []
        for u in self._users:
            if search and not (search in u.username.lower() or search in u.full_name.lower() or (u.email and search in u.email.lower())): continue
            if role_id is not None and u.role_id != role_id: continue
            actual_status = "locked" if u.is_locked else ("active" if u.is_active else "inactive")
            if status is not None and actual_status != status: continue
            if password_change is not None and bool(u.force_password_change) != password_change: continue
            filtered.append(u)
        self._filtered = filtered
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
                "security": "Locked" if user.is_locked else ("Change password" if user.force_password_change else "OK"),
                "_id": user.id,
            })
        self.data_table.set_data(data, len(data))

    def _on_search(self, text: str) -> None:
        self._apply_filters()

    def _on_row_double_clicked(self, row: int) -> None:
        if row < len(self._filtered):
            # Read-only users can safely inspect details; editing is separately permission-guarded.
            if not self._write_enabled:
                self._show_user_detail(self._filtered[row].id)
                return
            self._show_user_detail(self._filtered[row].id)

    def _on_context_menu(self, pos, row: int) -> None:
        if row < 0 or row >= len(self._filtered):
            return
        user = self._filtered[row]
        menu = QMenu(self)
        detail_action = QAction("View Details", self)
        detail_action.triggered.connect(lambda: self._show_user_detail(user.id))
        menu.addAction(detail_action)
        can_create = self._service.has_permission(PermissionDefinitions.USER_CREATE)
        can_update = self._service.has_permission(PermissionDefinitions.USER_UPDATE)
        can_reset = self._service.has_permission(PermissionDefinitions.USER_RESET_PASSWORD)
        edit_action = QAction("Edit", self)
        edit_action.setEnabled(self._write_enabled and can_update)
        edit_action.triggered.connect(lambda: self._show_edit_dialog(user.id))
        menu.addAction(edit_action)

        reset_action = QAction("Reset Password", self)
        reset_action.setEnabled(self._write_enabled and can_reset)
        reset_action.triggered.connect(lambda: self._reset_password(user.id))
        menu.addAction(reset_action)

        menu.addSeparator()

        if user.is_active:
            deactivate_action = QAction("Deactivate", self)
            deactivate_action.setEnabled(self._write_enabled and can_update)
            deactivate_action.triggered.connect(lambda: self._toggle_active(user.id, False))
            menu.addAction(deactivate_action)
        else:
            activate_action = QAction("Activate", self)
            activate_action.setEnabled(self._write_enabled and can_update)
            activate_action.triggered.connect(lambda: self._toggle_active(user.id, True))
            menu.addAction(activate_action)

        if user.is_locked:
            unlock_action = QAction("Unlock", self)
            unlock_action.setEnabled(self._write_enabled and can_update)
            unlock_action.triggered.connect(lambda: self._unlock_user(user.id))
            menu.addAction(unlock_action)

        menu.exec(pos)

    def _show_user_detail(self, user_id: int) -> None:
        user = self._service.get_user(user_id)
        if user is None: return
        role = user.role.display_name if user.role else "No role"
        permissions = sorted(user.permissions)
        details = (f"Username: {user.username}\nName: {user.full_name}\nEmail: {user.email or '-'}\nPhone: {user.phone or '-'}\n\n"
                   f"Role: {role}\nStatus: {'Locked' if user.is_locked else ('Active' if user.is_active else 'Inactive')}\n"
                   f"Last login: {user.last_login.strftime('%d/%m/%Y %H:%M') if user.last_login else '-'}\n"
                   f"Login attempts: {user.login_attempts}\nPassword change required: {'Yes' if user.force_password_change else 'No'}\n\n"
                   f"Permissions ({len(permissions)}):\n" + "\n".join(permissions or ['No permissions']))
        QMessageBox.information(self, "User Profile", details)

    def _show_add_dialog(self) -> None:
        if not self._service.has_permission(PermissionDefinitions.USER_CREATE):
            notify(self._notification_service, "Permission denied: user.create is required.", "warning"); return
        if not can_write(self._collaboration_manager):
            notify(self._notification_service, "You must be in WRITE mode to add a user.", "warning")
            return
        dialog = UserFormDialog(self._service, parent=self)
        if dialog.exec() == UserFormDialog.DialogCode.Accepted:
            self.refresh()

    def _show_edit_dialog(self, user_id: int) -> None:
        if not self._service.has_permission(PermissionDefinitions.USER_UPDATE):
            notify(self._notification_service, "Permission denied.", "warning")
            return
        if not can_write(self._collaboration_manager):
            notify(self._notification_service, "You must be in WRITE mode to edit a user.", "warning")
            return
        dialog = UserFormDialog(self._service, user_id=user_id, parent=self)
        if dialog.exec() == UserFormDialog.DialogCode.Accepted:
            self.refresh()

    def _reset_password(self, user_id: int) -> None:
        if not self._service.has_permission(PermissionDefinitions.USER_RESET_PASSWORD):
            notify(self._notification_service, "Permission denied.", "warning")
            return
        if not can_write(self._collaboration_manager):
            notify(self._notification_service, "You must be in WRITE mode to reset password.", "warning")
            return
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
        if not self._service.has_permission(PermissionDefinitions.USER_UPDATE):
            notify(self._notification_service, "Permission denied.", "warning")
            return
        if not can_write(self._collaboration_manager):
            notify(self._notification_service, "You must be in WRITE mode to change user status.", "warning")
            return
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
            except UserLifecycleError as e:
                QMessageBox.warning(self, "Action blocked", str(e))
            except Exception as e:
                logger.exception(f"{action} failed")
                QMessageBox.critical(self, "Error", str(e))

    def _unlock_user(self, user_id: int) -> None:
        if not self._service.has_permission(PermissionDefinitions.USER_UPDATE):
            notify(self._notification_service, "Permission denied.", "warning")
            return
        if not can_write(self._collaboration_manager):
            notify(self._notification_service, "You must be in WRITE mode to unlock a user.", "warning")
            return
        try:
            self._service.unlock_user(user_id)
            self.refresh()
            QMessageBox.information(self, "Unlocked", "User account has been unlocked.")
        except Exception as e:
            logger.exception("Unlock failed")
            QMessageBox.critical(self, "Error", str(e))

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self.add_btn.setEnabled(self._write_enabled)