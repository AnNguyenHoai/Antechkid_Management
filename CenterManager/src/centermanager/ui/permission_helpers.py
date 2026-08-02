# -*- coding: utf-8 -*-
"""
Permission helpers for UI components - menu visibility, route guards, etc.
"""
from typing import Optional, List, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QWidget, QMenu, QPushButton

from centermanager.core.current_user import get_current_user
from centermanager.services.permission_service import PermissionService
from centermanager.models.user import User


class UIPermissionHelper:
    """
    Helper for UI permission checking.
    
    Usage:
        helper = UIPermissionHelper(session_factory)
        
        # Hide a menu item if user doesn't have permission
        helper.control_visibility(menu_item, "finance.view")
        
        # Check permission for conditional rendering
        if helper.has_permission("finance.view"):
            show_finance_tab()
    """

    def __init__(self, session_factory):
        self._session_factory = session_factory
        self._permission_service = PermissionService(session_factory)

    def has_permission(self, permission_name: str, user: Optional[User] = None) -> bool:
        """Check if the current user has a permission."""
        return self._permission_service.has_permission(permission_name, user)

    def has_any_permission(self, permission_names: List[str], user: Optional[User] = None) -> bool:
        """Check if the user has any of the given permissions."""
        return self._permission_service.has_any_permission(permission_names, user)

    def get_current_user(self) -> Optional[User]:
        """Get the current user."""
        return get_current_user()

    def control_visibility(self, widget: QWidget, permission_name: str) -> None:
        """Set widget visibility based on permission. Hidden if permission is not granted."""
        widget.setVisible(self.has_permission(permission_name))

    def control_action_visibility(self, action: QAction, permission_name: str) -> None:
        """Set QAction visibility based on permission."""
        action.setVisible(self.has_permission(permission_name))

    def control_menu_visibility(self, menu: QMenu, permission_name: str) -> None:
        """Set QMenu visibility based on permission."""
        menu.menuAction().setVisible(self.has_permission(permission_name))

    def control_button_visibility(self, button: QPushButton, permission_name: str) -> None:
        """Set QPushButton visibility based on permission."""
        button.setVisible(self.has_permission(permission_name))

    def require_for_callback(self, permission_name: str, callback: Callable) -> Optional[Callable]:
        """
        Wrap a callback with permission check.
        Returns the wrapped callback or None if permission not granted.
        """
        if not self.has_permission(permission_name):
            return None

        def wrapped(*args, **kwargs):
            if not self.has_permission(permission_name):
                return
            return callback(*args, **kwargs)
        return wrapped


def get_menu_items_for_role(role_name: Optional[str]) -> List[dict]:
    all_items = [
        {"id": "dashboard", "icon": "📊", "label": "Dashboard", "permission": None},
        {"id": "student", "icon": "👨‍🎓", "label": "Student Workspace", "permission": None},
        {"id": "teacher", "icon": "👨‍🏫", "label": "Teacher Workspace", "permission": "teacher.view"},
        {"id": "class", "icon": "📚", "label": "Class Workspace", "permission": "class.view"},
        {"id": "finance", "icon": "💰", "label": "Finance Workspace", "permission": "finance.view"},
        {"id": "reports", "icon": "📈", "label": "Reports", "permission": "report.view"},
        {"id": "settings", "icon": "⚙️", "label": "Settings", "permission": "setting.update"},
    ]

    if role_name is None:
        return [item for item in all_items if item["permission"] is None]

    if role_name == "admin":
        return all_items

    if role_name == "teacher":
        return [
            item for item in all_items
            if item["permission"] is None
            or item["permission"] in ["teacher.view", "class.view", "report.view"]
        ]

    if role_name == "reception":
        return [
            item for item in all_items
            if item["permission"] is None
            or item["permission"] in ["class.view"]
        ]

    return [item for item in all_items if item["permission"] is None]