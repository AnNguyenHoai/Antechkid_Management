# -*- coding: utf-8 -*-
"""
TeacherAssignmentDialog - assign/unassign teacher to classes.
"""
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox
)

from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService
from centermanager.core.current_user import get_current_user
from centermanager.models.role import RoleDefinitions


class TeacherAssignmentDialog(QDialog):
    assignments_changed = Signal()
    def __init__(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_id: int,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        teacher_is_active: bool = True,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._assignment_service = assignment_service
        self._teacher_id = teacher_id
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._teacher_is_active = teacher_is_active
        self._all_classes: List = []
        self._assigned_ids: List[int] = []

        self.setWindowTitle("Manage Class Assignments")
        self.setMinimumSize(400, 300)
        self.setModal(True)

        self._setup_ui()
        self._load_data()
        self._update_write_state()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Available classes
        layout.addWidget(QLabel("Available Classes"))
        self.available_list = QListWidget()
        self.available_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.available_list)

        # Buttons
        btn_layout = QHBoxLayout()
        self.assign_btn = QPushButton("→ Assign")
        self.assign_btn.clicked.connect(self._assign_selected)
        self.unassign_btn = QPushButton("← Unassign")
        self.unassign_btn.clicked.connect(self._unassign_selected)
        btn_layout.addWidget(self.assign_btn)
        btn_layout.addWidget(self.unassign_btn)
        layout.addLayout(btn_layout)

        # Assigned classes
        layout.addWidget(QLabel("Assigned Classes"))
        self.assigned_list = QListWidget()
        self.assigned_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.assigned_list)

        # Done
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self.accept)
        layout.addWidget(done_btn)

    def _can_manage_class_assignments(self) -> bool:
        user = get_current_user()
        role_name = (
            getattr(getattr(user, "role", None), "name", None)
            if user is not None
            else None
        )
        return role_name in {
            RoleDefinitions.ADMIN,
            RoleDefinitions.MANAGER,
        }

    def _update_write_state(self) -> None:
        role_allowed = self._can_manage_class_assignments()
        can_assign = self._teacher_is_active and role_allowed
        self.assign_btn.setEnabled(can_assign)
        self.unassign_btn.setEnabled(role_allowed)

        if not role_allowed:
            message = "Only Admin or Manager accounts can manage teacher class assignments."
            self.assign_btn.setToolTip(message)
            self.unassign_btn.setToolTip(message)
        elif not self._teacher_is_active:
            self.assign_btn.setToolTip(
                "Inactive teachers cannot accept new class assignments."
            )

    def _ensure_write(self, action: str) -> bool:
        if self._collaboration_manager.ensure_write():
            return True
        self._notification_service.notify(
            f"You must be in WRITE mode to {action}.", "warning"
        )
        return False

    def _load_data(self) -> None:
        self._all_classes = self._assignment_service.list_available_classes()
        self._assigned_ids = self._assignment_service.get_assigned_classes(self._teacher_id)

        self._update_lists()

    def _update_lists(self) -> None:
        self.available_list.clear()
        self.assigned_list.clear()

        assigned_set = set(self._assigned_ids)

        for cls in self._all_classes:
            if cls.id in assigned_set:
                item = QListWidgetItem(cls.name)
                item.setData(Qt.ItemDataRole.UserRole, cls.id)
                self.assigned_list.addItem(item)
            else:
                item = QListWidgetItem(cls.name)
                item.setData(Qt.ItemDataRole.UserRole, cls.id)
                self.available_list.addItem(item)

    def _assign_selected(self) -> None:
        if not self._can_manage_class_assignments():
            self._notification_service.notify(
                "Only Admin or Manager accounts can assign classes.",
                "warning",
            )
            return
        if not self._teacher_is_active:
            self._notification_service.notify(
                "Inactive teachers cannot accept new class assignments.", "warning"
            )
            return
        if not self._ensure_write("assign classes"):
            return
        items = self.available_list.selectedItems()
        for item in items:
            class_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                self._assignment_service.assign_teacher_to_class(self._teacher_id, class_id)
                self._assigned_ids.append(class_id)
                self.assignments_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
        self._update_lists()

    def _unassign_selected(self) -> None:
        if not self._can_manage_class_assignments():
            self._notification_service.notify(
                "Only Admin or Manager accounts can unassign classes.",
                "warning",
            )
            return
        if not self._ensure_write("unassign classes"):
            return
        items = self.assigned_list.selectedItems()
        for item in items:
            class_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                self._assignment_service.unassign_teacher_from_class(self._teacher_id, class_id)
                self._assigned_ids.remove(class_id)
                self.assignments_changed.emit()
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
        self._update_lists()