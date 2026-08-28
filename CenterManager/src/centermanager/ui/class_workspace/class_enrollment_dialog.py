# -*- coding: utf-8 -*-
"""
ClassEnrollmentDialog - enroll/remove student from class.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox
)

from centermanager.services.class_service import ClassService
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService

logger = logging.getLogger(__name__)


class ClassEnrollmentDialog(QDialog):
    enrollment_changed = Signal(int)
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
        self._all_students: List = []
        self._enrolled_ids: List[int] = []

        self.setWindowTitle("Manage Students")
        self.setMinimumSize(450, 400)
        self.setModal(True)

        self._setup_ui()
        self._load_data()
        self._update_write_state()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)

        # Search
        search_layout = QHBoxLayout()
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search students...")
        self.search_edit.textChanged.connect(self._filter_students)
        search_layout.addWidget(self.search_edit)
        layout.addLayout(search_layout)

        # Available students
        layout.addWidget(QLabel("Available Students"))
        self.available_list = QListWidget()
        self.available_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.available_list)

        # Buttons
        btn_layout = QHBoxLayout()
        self.enroll_btn = QPushButton("→ Enroll")
        self.enroll_btn.clicked.connect(self._enroll_selected)
        btn_layout.addStretch()
        btn_layout.addWidget(self.enroll_btn)

        # Enrolled students
        layout.addWidget(QLabel("Enrolled Students"))
        self.enrolled_list = QListWidget()
        self.enrolled_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.enrolled_list)

        self.remove_btn = QPushButton("← Remove")
        self.remove_btn.clicked.connect(self._remove_selected)

        btn_layout2 = QHBoxLayout()
        btn_layout2.addStretch()
        btn_layout2.addWidget(self.remove_btn)

        layout.addLayout(btn_layout)
        layout.addLayout(btn_layout2)

        # Done
        done_btn = QPushButton("Done")
        done_btn.clicked.connect(self.accept)
        layout.addWidget(done_btn)

    def _ensure_enrollment_write(self, action: str) -> bool:
        if not self._collaboration_manager.ensure_write():
            self._notification_service.notify(f"You must be in WRITE mode to {action}.", "warning")
            return False
        return True

    def _update_write_state(self) -> None:
        enabled = self._collaboration_manager.ensure_write()
        self.enroll_btn.setEnabled(enabled)
        self.remove_btn.setEnabled(enabled)

    def _load_data(self) -> None:
        self._all_students = self._class_service.list_active_students()
        class_obj = self._class_service.get_class_with_details(self._class_id)
        self._enrolled_ids = [s.id for s in self._class_service.get_enrolled_students(self._class_id)]
        self._update_lists()

    def _filter_students(self, text: str) -> None:
        self._update_lists(text)

    def _update_lists(self, search_text: str = "") -> None:
        self.available_list.clear()
        self.enrolled_list.clear()

        enrolled_set = set(self._enrolled_ids)

        for s in self._all_students:
            if search_text and search_text.lower() not in s.full_name.lower() and search_text.lower() not in s.student_code.lower():
                continue
            display = f"{s.full_name} ({s.student_code})"
            if s.id in enrolled_set:
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, s.id)
                self.enrolled_list.addItem(item)
            else:
                item = QListWidgetItem(display)
                item.setData(Qt.ItemDataRole.UserRole, s.id)
                self.available_list.addItem(item)

    def _enroll_selected(self) -> None:
        if not self._ensure_enrollment_write("enroll students"):
            return
        items = self.available_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "Warning", "Please select at least one student.")
            return

        for item in items:
            student_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                logger.info(f"Enrolling student {student_id} into class {self._class_id}")
                self._class_service.enroll_student(self._class_id, student_id)
                self._enrolled_ids.append(student_id)
                self.enrollment_changed.emit(self._class_id)
                logger.info(f"Successfully enrolled student {student_id}")
            except Exception as e:
                logger.exception(f"Failed to enroll student {student_id}: {e}")
                QMessageBox.warning(self, "Enrollment Error", f"Failed to enroll student: {str(e)}")

        self._update_lists()

    def _remove_selected(self) -> None:
        if not self._ensure_enrollment_write("remove students"):
            return
        items = self.enrolled_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "Warning", "Please select at least one student.")
            return

        for item in items:
            student_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                logger.info(f"Removing student {student_id} from class {self._class_id}")
                self._class_service.remove_student(self._class_id, student_id)
                self._enrolled_ids.remove(student_id)
                self.enrollment_changed.emit(self._class_id)
                logger.info(f"Successfully removed student {student_id}")
            except Exception as e:
                logger.exception(f"Failed to remove student {student_id}: {e}")
                QMessageBox.warning(self, "Removal Error", f"Failed to remove student: {str(e)}")

        self._update_lists()