# -*- coding: utf-8 -*-
"""
ClassEnrollmentDialog - enroll/remove student from class.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QMessageBox, QInputDialog
)

from centermanager.services.class_service import ClassService
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.notification import NotificationService
from centermanager.ui.student_workspace.enrollment_pricing_dialog import EnrollmentPricingDialog

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
        self.enroll_btn = QPushButton("→ Enroll / Restore")
        self.enroll_btn.clicked.connect(self._enroll_selected)
        btn_layout.addStretch()
        btn_layout.addWidget(self.enroll_btn)

        # Enrolled students
        layout.addWidget(QLabel("Enrolled Students"))
        self.enrolled_list = QListWidget()
        self.enrolled_list.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        layout.addWidget(self.enrolled_list)

        self.remove_btn = QPushButton("← Withdraw")
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

    def _ask_existing_enrollment_action(self, enrollment) -> str:
        box = QMessageBox(self)
        box.setWindowTitle("Existing Enrollment History")
        box.setIcon(QMessageBox.Icon.Question)
        box.setText(
            "This student has a withdrawn Enrollment in this class.\n\n"
            f"Enrollment #{enrollment.id}\n"
            f"Session range: {enrollment.enrolled_from_session or '-'}"
            f"–{enrollment.enrolled_until_session or '-'}\n"
            f"Withdrawn on: {enrollment.end_date or '-'}\n\n"
            "Restore the existing contract if the withdrawal was a mistake. "
            "Create a new Enrollment only for a genuine re-enrollment."
        )
        restore_btn = box.addButton("Restore existing", QMessageBox.ButtonRole.AcceptRole)
        new_btn = box.addButton("Create new Enrollment", QMessageBox.ButtonRole.ActionRole)
        box.addButton(QMessageBox.StandardButton.Cancel)
        box.exec()
        clicked = box.clickedButton()
        if clicked is restore_btn:
            return "restore"
        if clicked is new_btn:
            return "new"
        return "cancel"

    def _enroll_selected(self) -> None:
        if not self._ensure_enrollment_write("enroll students"):
            return
        items = self.available_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "Warning", "Please select at least one student.")
            return

        enrollment_kwargs = None
        for item in items:
            student_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                candidate = self._class_service.get_latest_restorable_enrollment(
                    self._class_id, student_id
                )
                if candidate is not None:
                    action = self._ask_existing_enrollment_action(candidate)
                    if action == "cancel":
                        continue
                    if action == "restore":
                        reason, accepted = QInputDialog.getText(
                            self,
                            "Restore Enrollment",
                            "Reason for restoring this withdrawn Enrollment:",
                        )
                        if not accepted:
                            continue
                        reason = reason.strip()
                        if not reason:
                            QMessageBox.warning(
                                self, "Restore Enrollment", "A restore reason is required."
                            )
                            continue
                        self._class_service.restore_student(
                            self._class_id,
                            student_id,
                            candidate.id,
                            reason=reason,
                        )
                        if student_id not in self._enrolled_ids:
                            self._enrolled_ids.append(student_id)
                        self.enrollment_changed.emit(self._class_id)
                        logger.info("Restored enrollment %s for student %s", candidate.id, student_id)
                        continue

                if enrollment_kwargs is None:
                    pricing = EnrollmentPricingDialog(
                        self._class_service,
                        self._class_id,
                        parent=self,
                    )
                    if pricing.exec() != QDialog.DialogCode.Accepted:
                        break
                    enrollment_kwargs = pricing.enrollment_kwargs()

                logger.info("Enrolling student %s into class %s", student_id, self._class_id)
                self._class_service.enroll_student(
                    self._class_id,
                    student_id,
                    **enrollment_kwargs,
                )
                if student_id not in self._enrolled_ids:
                    self._enrolled_ids.append(student_id)
                self.enrollment_changed.emit(self._class_id)
                logger.info("Successfully enrolled student %s", student_id)
            except Exception as e:
                logger.exception("Failed to enroll/restore student %s: %s", student_id, e)
                QMessageBox.warning(
                    self, "Enrollment Error", f"Failed to enroll/restore student: {str(e)}"
                )

        self._update_lists()
    def _remove_selected(self) -> None:
        # Keep the legacy authorization action key stable; the user-facing action is Withdraw.
        if not self._ensure_enrollment_write("remove students"):
            return
        items = self.enrolled_list.selectedItems()
        if not items:
            QMessageBox.warning(self, "Warning", "Please select at least one student.")
            return

        names = ", ".join(item.text() for item in items)
        answer = QMessageBox.question(
            self,
            "Withdraw from class",
            "This action records a real withdrawal and keeps attendance, tuition, "
            "payment and Enrollment history.\n\n"
            f"Withdraw: {names}?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        reason, accepted = QInputDialog.getText(
            self,
            "Withdrawal reason",
            "Reason for withdrawal:",
        )
        if not accepted:
            return
        reason = reason.strip()
        if not reason:
            QMessageBox.warning(self, "Withdrawal reason", "A withdrawal reason is required.")
            return

        for item in items:
            student_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                logger.info("Withdrawing student %s from class %s", student_id, self._class_id)
                self._class_service.remove_student(
                    self._class_id,
                    student_id,
                    reason=reason,
                )
                if student_id in self._enrolled_ids:
                    self._enrolled_ids.remove(student_id)
                self.enrollment_changed.emit(self._class_id)
                logger.info("Successfully withdrew student %s", student_id)
            except Exception as e:
                logger.exception("Failed to withdraw student %s: %s", student_id, e)
                QMessageBox.warning(
                    self, "Withdrawal Error", f"Failed to withdraw student: {str(e)}"
                )

        self._update_lists()
