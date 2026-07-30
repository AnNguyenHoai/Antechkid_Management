# -*- coding: utf-8 -*-
"""
ClassFormDialog - create or edit a class.
"""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QSpinBox, QPushButton, QHBoxLayout,
    QMessageBox, QWidget
)

from centermanager.services.class_service import ClassService, ClassValidationError


logger = logging.getLogger(__name__)


class ClassFormDialog(QDialog):
    def __init__(
        self,
        class_service: ClassService,
        class_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = class_service
        self._class_id = class_id
        self._is_edit = class_id is not None

        self.setWindowTitle("Edit Class" if self._is_edit else "Add Class")
        self.setMinimumWidth(450)
        self.setModal(True)

        self._setup_ui()
        if self._is_edit:
            self._load_class()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # Name
        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Class name")
        form.addRow("Class Name *", self.name_edit)

        # Course
        self.course_edit = QLineEdit()
        self.course_edit.setPlaceholderText("Course name")
        form.addRow("Course", self.course_edit)

        # Start Date
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.start_date_edit.setSpecialValueText("")
        self.start_date_edit.setDate(QDate.currentDate())
        form.addRow("Start Date", self.start_date_edit)

        # End Date
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDisplayFormat("dd/MM/yyyy")
        self.end_date_edit.setSpecialValueText("")
        self.end_date_edit.setDate(QDate.currentDate().addDays(30))
        form.addRow("End Date", self.end_date_edit)

        # Capacity
        self.capacity_spin = QSpinBox()
        self.capacity_spin.setRange(0, 999)
        self.capacity_spin.setSpecialValueText("Unlimited")
        form.addRow("Capacity", self.capacity_spin)

        # Status
        self.status_combo = QComboBox()
        self.status_combo.addItems(["ACTIVE", "INACTIVE"])
        form.addRow("Status", self.status_combo)

        layout.addLayout(form)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Save")
        self.save_btn.setFixedWidth(100)
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.setFixedWidth(100)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _load_class(self) -> None:
        try:
            class_obj = self._service.get_class(self._class_id)
            self.name_edit.setText(class_obj.name)
            self.course_edit.setText(class_obj.course or "")
            if class_obj.start_date:
                qdate = QDate(class_obj.start_date.year, class_obj.start_date.month, class_obj.start_date.day)
                self.start_date_edit.setDate(qdate)
            if class_obj.end_date:
                qdate = QDate(class_obj.end_date.year, class_obj.end_date.month, class_obj.end_date.day)
                self.end_date_edit.setDate(qdate)
            self.capacity_spin.setValue(class_obj.capacity or 0)
            status_idx = self.status_combo.findText(class_obj.status or "ACTIVE")
            if status_idx >= 0:
                self.status_combo.setCurrentIndex(status_idx)
        except Exception as e:
            logger.exception("Error loading class")
            QMessageBox.critical(self, "Error", "Could not load class data.")
            self.reject()

    def _save(self) -> None:
        name = self.name_edit.text().strip()
        course = self.course_edit.text().strip() or None
        start_date = self.start_date_edit.date().toPython() if self.start_date_edit.date().isValid() else None
        end_date = self.end_date_edit.date().toPython() if self.end_date_edit.date().isValid() else None
        capacity = self.capacity_spin.value() or None
        status = self.status_combo.currentText()

        try:
            if self._is_edit:
                self._service.update_class(
                    class_id=self._class_id,
                    name=name,
                    course=course,
                    start_date=start_date,
                    end_date=end_date,
                    capacity=capacity,
                    status=status,
                )
            else:
                self._service.create_class(
                    name=name,
                    course=course,
                    start_date=start_date,
                    end_date=end_date,
                    capacity=capacity,
                    status=status,
                )
            self.accept()
        except ClassValidationError as e:
            QMessageBox.warning(self, "Validation Error", str(e))
        except Exception as e:
            logger.exception("Error saving class")
            QMessageBox.critical(self, "Error", "An unexpected error occurred.")