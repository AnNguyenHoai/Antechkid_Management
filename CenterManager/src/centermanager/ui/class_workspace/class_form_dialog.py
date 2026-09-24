# -*- coding: utf-8 -*-
"""ClassFormDialog - create or edit a class course contract."""
from __future__ import annotations

import calendar
import logging
from datetime import date, timedelta
from decimal import Decimal
from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from centermanager.core.clock import get_clock
from centermanager.services.class_service import ClassService, ClassValidationError
from centermanager.ui.design_system.feedback import FeedbackController, FeedbackHost


logger = logging.getLogger(__name__)


def _add_calendar_months(value: date, months: int) -> date:
    """Add calendar months without treating a month as a fixed number of weeks."""
    month_index = value.month - 1 + months
    year = value.year + month_index // 12
    month = month_index % 12 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def _planned_end_date(start_date: date, duration_months: int) -> Optional[date]:
    """Return the inclusive planned course end from calendar-month duration."""
    if duration_months <= 0:
        return None
    return _add_calendar_months(start_date, duration_months) - timedelta(days=1)


def _unit_fee(course_fee: int, planned_sessions: int) -> Optional[Decimal]:
    if course_fee < 0 or planned_sessions <= 0:
        return None
    return Decimal(course_fee) / Decimal(planned_sessions)


def _format_vnd(value: Decimal | int) -> str:
    rounded = Decimal(value).quantize(Decimal("1"))
    return f"{int(rounded):,} VND".replace(",", ".")


class ClassFormDialog(QDialog):
    def __init__(
        self,
        class_service: ClassService,
        class_id: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = class_service
        self._class_id = class_id
        self._is_edit = class_id is not None
        self._loaded_contract_complete = False
        self._loaded_course_fee: Optional[int] = None
        self._feedback = FeedbackController(self)

        self.setWindowTitle("Edit Class" if self._is_edit else "Add Class")
        self.setMinimumWidth(520)
        self.setModal(True)

        self._setup_ui()
        if self._is_edit:
            self._load_class()
        else:
            self._refresh_course_preview()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.feedback_host = FeedbackHost(self._feedback, parent=self)
        layout.addWidget(self.feedback_host)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("Class name")
        form.addRow("Class Name *", self.name_edit)

        self.course_edit = QLineEdit()
        self.course_edit.setPlaceholderText("Course name")
        form.addRow("Course", self.course_edit)

        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDisplayFormat("dd/MM/yyyy")
        today = get_clock().today()
        self.start_date_edit.setDate(QDate(today.year, today.month, today.day))
        form.addRow("Start Date *", self.start_date_edit)

        self.duration_months_spin = QSpinBox()
        self.duration_months_spin.setRange(0, 60)
        self.duration_months_spin.setSpecialValueText("Not set")
        self.duration_months_spin.setSuffix(" months")
        form.addRow("Course Duration *", self.duration_months_spin)

        self.sessions_per_week_spin = QSpinBox()
        self.sessions_per_week_spin.setRange(0, 14)
        self.sessions_per_week_spin.setSpecialValueText("Not set")
        self.sessions_per_week_spin.setSuffix(" sessions/week")
        form.addRow("Sessions / Week *", self.sessions_per_week_spin)

        self.planned_sessions_spin = QSpinBox()
        self.planned_sessions_spin.setRange(0, 1000)
        self.planned_sessions_spin.setSpecialValueText("Not set")
        self.planned_sessions_spin.setSuffix(" sessions")
        form.addRow("Planned Sessions *", self.planned_sessions_spin)

        self.course_fee_spin = QSpinBox()
        self.course_fee_spin.setRange(0, 99999999)
        self.course_fee_spin.setSuffix(" VND")
        self.course_fee_spin.setValue(0)
        form.addRow("Course Fee *", self.course_fee_spin)

        self.unit_fee_value = QLabel("—")
        form.addRow("Tuition / Session", self.unit_fee_value)

        self.planned_end_value = QLabel("—")
        form.addRow("Planned End", self.planned_end_value)

        self.course_summary = QLabel()
        self.course_summary.setWordWrap(True)
        form.addRow("Course Summary", self.course_summary)

        self.capacity_spin = QSpinBox()
        self.capacity_spin.setRange(0, 999)
        self.capacity_spin.setSpecialValueText("Unlimited")
        form.addRow("Capacity", self.capacity_spin)

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

        self.start_date_edit.dateChanged.connect(self._refresh_course_preview)
        self.duration_months_spin.valueChanged.connect(self._refresh_course_preview)
        self.sessions_per_week_spin.valueChanged.connect(self._refresh_course_preview)
        self.planned_sessions_spin.valueChanged.connect(self._refresh_course_preview)
        self.course_fee_spin.valueChanged.connect(self._refresh_course_preview)
        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)

    def _load_class(self) -> None:
        try:
            class_obj = self._service.get_class(self._class_id)
            self.name_edit.setText(class_obj.name)
            self.course_edit.setText(class_obj.course or "")
            self._loaded_contract_complete = class_obj.has_course_contract
            self._loaded_course_fee = class_obj.course_fee
            self.course_fee_spin.setValue(class_obj.course_fee or 0)
            self.duration_months_spin.setValue(class_obj.duration_months or 0)
            self.planned_sessions_spin.setValue(class_obj.planned_sessions or 0)
            self.sessions_per_week_spin.setValue(class_obj.sessions_per_week or 0)
            if class_obj.start_date:
                self.start_date_edit.setDate(
                    QDate(
                        class_obj.start_date.year,
                        class_obj.start_date.month,
                        class_obj.start_date.day,
                    )
                )
            self.capacity_spin.setValue(class_obj.capacity or 0)
            status_idx = self.status_combo.findText(class_obj.status or "ACTIVE")
            if status_idx >= 0:
                self.status_combo.setCurrentIndex(status_idx)
            self._refresh_course_preview()
        except Exception:
            logger.exception("Error loading class")
            QMessageBox.critical(self, "Error", "Could not load class data.")
            self.reject()

    def _course_contract_is_complete(self) -> bool:
        return (
            self.duration_months_spin.value() > 0
            and self.sessions_per_week_spin.value() > 0
            and self.planned_sessions_spin.value() > 0
        )

    def _course_contract_was_touched(self) -> bool:
        if not self._is_edit:
            return True
        if self._loaded_contract_complete:
            return True
        return (
            self.duration_months_spin.value() > 0
            or self.sessions_per_week_spin.value() > 0
            or self.planned_sessions_spin.value() > 0
            or self.course_fee_spin.value() != (self._loaded_course_fee or 0)
        )

    def _refresh_course_preview(self, *_args) -> None:
        start = self.start_date_edit.date().toPython()
        duration = self.duration_months_spin.value()
        weekly = self.sessions_per_week_spin.value()
        planned = self.planned_sessions_spin.value()
        fee = self.course_fee_spin.value()

        per_session = _unit_fee(fee, planned)
        self.unit_fee_value.setText(_format_vnd(per_session) if per_session is not None else "—")

        planned_end = _planned_end_date(start, duration)
        self.planned_end_value.setText(
            planned_end.strftime("%d/%m/%Y") if planned_end is not None else "—"
        )

        if duration > 0 and weekly > 0 and planned > 0:
            self.course_summary.setText(
                f"{duration} months · {weekly} sessions/week · {planned} planned sessions · "
                f"{_format_vnd(fee)} total"
            )
        elif self._is_edit and not self._loaded_contract_complete:
            self.course_summary.setText(
                "Legacy class: course contract is incomplete. Existing data is preserved until "
                "duration, weekly frequency and planned sessions are explicitly provided."
            )
        else:
            self.course_summary.setText(
                "Enter duration, weekly frequency and planned sessions to complete the course contract."
            )

    def _validate_form_contract(self) -> bool:
        if not self._course_contract_was_touched():
            return True
        if not self._course_contract_is_complete():
            self._feedback.warning(
                "Duration, sessions per week and planned sessions must all be greater than zero.",
                title="Incomplete course contract",
                key="class-validation",
            )
            return False
        return True

    def _save(self) -> None:
        if not self._validate_form_contract():
            return

        self._feedback.clear("class-validation")
        name = self.name_edit.text().strip()
        course = self.course_edit.text().strip() or None
        start_date = self.start_date_edit.date().toPython()
        capacity = self.capacity_spin.value() or None
        status = self.status_combo.currentText()

        kwargs = {
            "name": name,
            "course": course,
            "start_date": start_date,
            "capacity": capacity,
            "status": status,
        }

        if self._course_contract_was_touched():
            duration_months = self.duration_months_spin.value()
            planned_sessions = self.planned_sessions_spin.value()
            sessions_per_week = self.sessions_per_week_spin.value()
            course_fee = self.course_fee_spin.value()
            kwargs.update(
                course_fee=course_fee,
                duration_months=duration_months,
                planned_sessions=planned_sessions,
                sessions_per_week=sessions_per_week,
                end_date=_planned_end_date(start_date, duration_months),
            )

        try:
            if self._is_edit:
                self._service.update_class(class_id=self._class_id, **kwargs)
            else:
                self._service.create_class(**kwargs)
            self.accept()
        except ClassValidationError as exc:
            self._feedback.warning(
                str(exc),
                title="Check class details",
                key="class-validation",
            )
        except Exception as exc:
            logger.exception("Error saving class")
            self._feedback.system_error(
                exc,
                message="We couldn't save the class. Please review the details and try again.",
                key="class-save",
            )
