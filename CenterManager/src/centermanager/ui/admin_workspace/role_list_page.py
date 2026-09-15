# -*- coding: utf-8 -*-
"""RoleListPage - Admin role and permission management."""
from typing import Optional, List

from PySide6.QtCore import Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QMenu, QMessageBox

from centermanager.models.role import Role
from centermanager.services.permission_service import PermissionService, RoleLifecycleError
from centermanager.ui.design_system import SearchBar, PrimaryButton, SecondaryButton
from centermanager.ui.shared import DataTable
from centermanager.ui.admin_workspace.access import can_write, notify
from centermanager.ui.admin_workspace.role_form_dialog import RoleFormDialog


class RoleListPage(QWidget):
    role_selected = Signal(int)

    def __init__(self, permission_service: PermissionService, collaboration_manager, notification_service, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._service = permission_service
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._write_enabled = can_write(collaboration_manager)
        self._roles: List[Role] = []
        self._filtered: List[Role] = []
        self._setup_ui(); self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self); layout.setContentsMargins(0, 0, 0, 0); layout.setSpacing(0)
        toolbar = QHBoxLayout()
        self.search_bar = SearchBar("Search roles..."); self.search_bar.text_changed.connect(lambda _: self._apply_filters())
        self.refresh_btn = SecondaryButton("🔄 Refresh"); self.refresh_btn.clicked.connect(self.refresh)
        self.add_btn = PrimaryButton("+ Add Role"); self.add_btn.clicked.connect(self._show_add)
        toolbar.addWidget(self.search_bar); toolbar.addWidget(self.refresh_btn); toolbar.addWidget(self.add_btn)
        layout.addLayout(toolbar)
        self.data_table = DataTable([
            {"key": "display_name", "label": "Role", "sortable": True},
            {"key": "name", "label": "Role Key", "sortable": True},
            {"key": "description", "label": "Description", "sortable": True},
            {"key": "permissions", "label": "Permissions", "sortable": True},
            {"key": "users", "label": "Users", "sortable": True},
            {"key": "type", "label": "Type", "sortable": True},
        ], page_size=20)
        self.data_table.row_double_clicked.connect(self._edit_row)
        self.data_table.context_menu_requested.connect(self._context_menu)
        layout.addWidget(self.data_table)

    def refresh(self):
        self._roles = self._service.get_all_roles(); self._apply_filters()

    def _apply_filters(self):
        q = self.search_bar.text().strip().lower()
        self._filtered = [r for r in self._roles if not q or q in r.name.lower() or q in r.display_name.lower() or q in (r.description or "").lower()]
        data = [{"display_name": r.display_name, "name": r.name, "description": r.description or "-", "permissions": len(r.permissions), "users": len(r.users), "type": "System" if r.is_system else "Custom", "_id": r.id} for r in self._filtered]
        self.data_table.set_data(data, len(data))

    def _edit_row(self, row):
        if 0 <= row < len(self._filtered) and self._write_enabled: self._show_edit(self._filtered[row].id)

    def _context_menu(self, pos, row):
        if not 0 <= row < len(self._filtered): return
        role = self._filtered[row]; menu = QMenu(self)
        edit = QAction("View / Edit", self); edit.setEnabled(self._write_enabled); edit.triggered.connect(lambda: self._show_edit(role.id)); menu.addAction(edit)
        if not role.is_system:
            delete = QAction("Delete", self); delete.setEnabled(self._write_enabled); delete.triggered.connect(lambda: self._delete(role)); menu.addAction(delete)
        menu.exec(pos)

    def _show_add(self):
        if not self._write_enabled: notify(self._notification_service, "You must be in WRITE mode to create a role.", "warning"); return
        dialog = RoleFormDialog(self._service, parent=self)
        if dialog.exec(): self.refresh()

    def _show_edit(self, role_id):
        dialog = RoleFormDialog(self._service, role_id, self)
        if dialog.exec(): self.refresh()

    def _delete(self, role):
        if not self._write_enabled: return
        if QMessageBox.question(self, "Delete Role", f"Delete role '{role.display_name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No) != QMessageBox.StandardButton.Yes: return
        try: self._service.delete_role(role.id); self.refresh()
        except RoleLifecycleError as exc: QMessageBox.warning(self, "Role", str(exc))
        except Exception as exc: QMessageBox.critical(self, "Error", str(exc))

    def set_write_enabled(self, enabled: bool):
        self._write_enabled = bool(enabled); self.add_btn.setEnabled(self._write_enabled)
