# -*- coding: utf-8 -*-
"""Search-first picker for exact tuition Enrollment identity."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QTimer, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from centermanager.services.income_service import IncomeService, TuitionEnrollmentChoice


class TuitionEnrollmentPicker(QWidget):
    """Search and select one exact Enrollment for a tuition payment."""

    selection_changed = Signal()

    def __init__(self, income_service: IncomeService, parent=None) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._selected: Optional[TuitionEnrollmentChoice] = None

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(6)

        search_row = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText(
            "Tìm theo tên, mã HS, SĐT phụ huynh, tên lớp hoặc khóa học..."
        )
        search_row.addWidget(self.search_edit, 1)

        self.include_historical = QCheckBox("Include historical enrollments", self)
        search_row.addWidget(self.include_historical)
        root.addLayout(search_row)

        self.results = QListWidget(self)
        self.results.setMinimumHeight(180)
        root.addWidget(self.results)

        self.selection_label = QLabel("Chưa chọn Enrollment học phí.", self)
        self.selection_label.setWordWrap(True)
        root.addWidget(self.selection_label)

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(250)
        self._debounce.timeout.connect(self.refresh)

        self.search_edit.textChanged.connect(lambda _text: self._debounce.start())
        self.include_historical.toggled.connect(lambda _checked: self.refresh())
        self.results.itemSelectionChanged.connect(self._on_selection_changed)

        self.refresh()

    @staticmethod
    def _money(value) -> str:
        return f"{value:,.0f} VND"

    @classmethod
    def _choice_label(cls, choice: TuitionEnrollmentChoice) -> str:
        if not choice.tuition_configured:
            balance = "Chưa cấu hình học phí"
        elif choice.balance_state == "OWED":
            balance = f"Còn phải đóng {cls._money(choice.debt_amount)}"
        elif choice.balance_state == "PREPAID":
            balance = f"Trả trước {cls._money(choice.prepaid_amount)}"
        else:
            balance = "Đã cân bằng học phí"

        course = f" · {choice.course_name}" if choice.course_name else ""
        return (
            f"{choice.student_name} · {choice.student_code}\n"
            f"{choice.class_name}{course} · {choice.enrollment_status} · "
            f"Enrollment #{choice.enrollment_id}\n"
            f"{balance}"
        )

    def refresh(self) -> None:
        previous_id = self.selected_enrollment_id()
        self.results.blockSignals(True)
        self.results.clear()
        self._selected = None

        try:
            choices = self._income_service.search_tuition_enrollment_choices(
                self.search_edit.text(),
                include_historical=self.include_historical.isChecked(),
                limit=20,
            )
        except Exception as exc:
            item = QListWidgetItem(f"Không thể tải Enrollment: {exc}")
            item.setData(256, None)
            self.results.addItem(item)
            self.results.blockSignals(False)
            self.selection_label.setText("Không thể tải Enrollment học phí.")
            self.selection_changed.emit()
            return

        selected_row = None
        for row, choice in enumerate(choices):
            item = QListWidgetItem(self._choice_label(choice))
            item.setData(256, choice)
            self.results.addItem(item)
            if previous_id is not None and choice.enrollment_id == previous_id:
                selected_row = row

        if not choices:
            item = QListWidgetItem("Không tìm thấy Enrollment phù hợp.")
            item.setData(256, None)
            self.results.addItem(item)

        self.results.blockSignals(False)
        if selected_row is not None:
            self.results.setCurrentRow(selected_row)
        else:
            self.selection_label.setText("Chưa chọn Enrollment học phí.")
            self.selection_changed.emit()

    def _on_selection_changed(self) -> None:
        item = self.results.currentItem()
        choice = item.data(256) if item is not None else None
        self._selected = choice if isinstance(choice, TuitionEnrollmentChoice) else None
        if self._selected is None:
            self.selection_label.setText("Chưa chọn Enrollment học phí.")
        else:
            self.selection_label.setText(
                f"Đã chọn: {self._selected.student_name} · "
                f"{self._selected.class_name} · Enrollment #{self._selected.enrollment_id}"
            )
        self.selection_changed.emit()

    def selected_choice(self) -> Optional[TuitionEnrollmentChoice]:
        return self._selected

    def selected_enrollment_id(self) -> Optional[int]:
        return self._selected.enrollment_id if self._selected is not None else None

    def clear_selection(self) -> None:
        self.results.clearSelection()
        self._selected = None
        self.selection_label.setText("Chưa chọn Enrollment học phí.")
        self.selection_changed.emit()


__all__ = ["TuitionEnrollmentPicker"]
