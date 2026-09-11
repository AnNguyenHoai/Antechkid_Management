# -*- coding: utf-8 -*-
"""
ClassAssignmentDialog - assign teacher to class.
"""
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox
)

from centermanager.services.class_service import ClassService
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService
from centermanager.core.current_user import get_current_user
from centermanager.models.role import RoleDefinitions


class ClassAssignmentDialog(QDialog):
    assignment_changed = Signal(int)
    def __init__(
        self,
        class_service: ClassService,
        class_id: int,
        collaboration_manager: CollaborationManager,
        notification_service: NotificationService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._class_service = class_service
        self._class_id = class_id
        self._collaboration_manager = collaboration_manager
        self._notification_service = notification_service
        self._all_teachers: List = []
        self._assigned_ids: List[int] = []

        self.setWindowTitle("Assign Teacher to Class")
        self.setMinimumSize(400, 300)
        self.setModal(True)

        self._setup_ui()
        self._load_data()
        self._update_write_state()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Available teachers
        layout.addWidget(QLabel("Available Teachers"))
        self.available_list = QListWidget()
        self.available_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.available_list)

        # Buttons
        btn_layout = QHBoxLayout()
        self.assign_btn = QPushButton("→ Assign")
        self.assign_btn.clicked.connect(self._assign_selected)
        btn_layout.addStretch()
        btn_layout.addWidget(self.assign_btn)

        # Assigned teachers
        layout.addWidget(QLabel("Assigned Teachers"))
        self.assigned_list = QListWidget()
        self.assigned_list.setSelectionMode(QListWidget.SelectionMode.SingleSelection)
        layout.addWidget(self.assigned_list)

        self.unassign_btn = QPushButton("← Unassign")
        self.unassign_btn.clicked.connect(self._unassign_selected)

        btn_layout2 = QHBoxLayout()
        btn_layout2.addStretch()
        btn_layout2.addWidget(self.unassign_btn)

        layout.addLayout(btn_layout)
        layout.addLayout(btn_layout2)

        # Done
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self.accept)
        layout.addWidget(done_btn)

    def _can_manage_assignments(self) -> bool:
        user = get_current_user()
        role_name = getattr(getattr(user, "role", None), "name", None) if user else None
        return role_name in {RoleDefinitions.ADMIN, RoleDefinitions.MANAGER}

    def _ensure_assignment_write(self, action: str) -> bool:
        if not self._can_manage_assignments():
            self._notification_service.notify(
                "Only Admin or Manager accounts can manage teacher class assignments.",
                "warning",
            )
            return False
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(f"You must be in WRITE mode to {action}.", "warning")
            return False
        return True

    def _update_write_state(self) -> None:
        enabled = self._can_manage_assignments() and self._collaboration_manager.ensure_write()
        self.assign_btn.setEnabled(enabled)
        self.unassign_btn.setEnabled(enabled)

    def _load_data(self) -> None:
        self._all_teachers = self._class_service.list_active_teachers()
        class_obj = self._class_service.get_class_with_details(self._class_id)
        self._assigned_ids = [t.id for t in class_obj.teachers]
        self._update_lists()

    def _update_lists(self) -> None:
        self.available_list.clear()
        self.assigned_list.clear()

        assigned_set = set(self._assigned_ids)

        for t in self._all_teachers:
            if t.id in assigned_set:
                item = QListWidgetItem(f"{t.full_name} ({t.teacher_code})")
                item.setData(Qt.ItemDataRole.UserRole, t.id)
                self.assigned_list.addItem(item)
            else:
                item = QListWidgetItem(f"{t.full_name} ({t.teacher_code})")
                item.setData(Qt.ItemDataRole.UserRole, t.id)
                self.available_list.addItem(item)

    def _assign_selected(self) -> None:
        if not self._ensure_assignment_write("assign a teacher"):
            return
        items = self.available_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "Warning", "Please select a teacher.")
            return
        item = items[0]
        teacher_id = item.data(Qt.ItemDataRole.UserRole)

        try:
            self._class_service.assign_teacher(self._class_id, teacher_id)
            self._assigned_ids.append(teacher_id)
            self._update_lists()
            self.assignment_changed.emit(self._class_id)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))

    def _unassign_selected(self) -> None:
        if not self._ensure_assignment_write("remove a teacher"):
            return
        items = self.assigned_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "Warning", "Please select a teacher.")
            return
        item = items[0]
        teacher_id = item.data(Qt.ItemDataRole.UserRole)

        try:
            self._class_service.remove_teacher(self._class_id, teacher_id)
            self._assigned_ids.remove(teacher_id)
            self._update_lists()
            self.assignment_changed.emit(self._class_id)
        except Exception as e:
            QMessageBox.warning(self, "Error", str(e))