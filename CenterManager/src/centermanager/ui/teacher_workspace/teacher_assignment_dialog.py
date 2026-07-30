# -*- coding: utf-8 -*-
"""
TeacherAssignmentDialog - assign/unassign teacher to classes.
"""
from typing import Optional, List

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QMessageBox
)

from centermanager.services.teacher_assignment_service import TeacherAssignmentService
from centermanager.repositories.class_repository import ClassRepository  # <-- sửa
from centermanager.database.engine import create_production_engine
from sqlalchemy.orm import sessionmaker


class TeacherAssignmentDialog(QDialog):
    def __init__(
        self,
        assignment_service: TeacherAssignmentService,
        teacher_id: int,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._assignment_service = assignment_service
        self._teacher_id = teacher_id
        self._all_classes: List = []
        self._assigned_ids: List[int] = []

        self.setWindowTitle("Manage Class Assignments")
        self.setMinimumSize(400, 300)
        self.setModal(True)

        self._setup_ui()
        self._load_data()

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

    def _load_data(self) -> None:
        engine = create_production_engine()
        session_factory = sessionmaker(bind=engine)

        with session_factory() as session:
            repo = ClassRepository(session)
            self._all_classes = repo.list_all()

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
        items = self.available_list.selectedItems()
        for item in items:
            class_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                self._assignment_service.assign_teacher_to_class(self._teacher_id, class_id)
                self._assigned_ids.append(class_id)
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
        self._update_lists()

    def _unassign_selected(self) -> None:
        items = self.assigned_list.selectedItems()
        for item in items:
            class_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                self._assignment_service.unassign_teacher_from_class(self._teacher_id, class_id)
                self._assigned_ids.remove(class_id)
            except Exception as e:
                QMessageBox.warning(self, "Error", str(e))
        self._update_lists()