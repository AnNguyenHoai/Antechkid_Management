# -*- coding: utf-8 -*-
"""
IncomeFormDialog - create or edit income, supporting both student and other sources.
"""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QDateEdit,
    QComboBox, QDoubleSpinBox, QPushButton, QHBoxLayout,
    QMessageBox, QWidget, QLabel
)

from centermanager.services.income_service import IncomeService, IncomeValidationError
from centermanager.services.student_service import StudentService
from centermanager.services.class_service import ClassService
from centermanager.core.current_user import get_current_user

logger = logging.getLogger(__name__)


class IncomeFormDialog(QDialog):
    def __init__(
        self,
        income_service: IncomeService,
        student_service: StudentService,
        class_service: ClassService,
        income_id: Optional[int] = None,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._income_id = income_id
        self._is_edit = income_id is not None

        self.setWindowTitle("Edit Income" if self._is_edit else "Add Income")
        self.setMinimumWidth(550)
        self.setModal(True)

        self._setup_ui()
        if self._is_edit:
            self._load_income()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(8)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        # ---- Source selection ----
        self.source_combo = QComboBox()
        self.source_combo.addItems(["Từ học sinh", "Nguồn khác"])
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        form.addRow("Nguồn thu *", self.source_combo)

        # ---- Student and Class ----
        self.student_combo = QComboBox()
        self._load_students()
        form.addRow("Học sinh *", self.student_combo)

        self.class_combo = QComboBox()
        self._load_classes()
        form.addRow("Lớp học *", self.class_combo)

        # ---- Other source description ----
        self.other_source_edit = QLineEdit()
        self.other_source_edit.setPlaceholderText("Ví dụ: Tiền quyên góp, Lãi ngân hàng, Tiền bán đồ cũ...")
        self.other_source_edit.setVisible(False)
        form.addRow("Mô tả nguồn khác", self.other_source_edit)

        # ---- Income fields (common) ----
        self.type_combo = QComboBox()
        for t in ["Tuition", "Book", "Robot Kit", "Material", "Other"]:
            self.type_combo.addItem(t)
        form.addRow("Loại thu *", self.type_combo)

        self.amount_spin = QDoubleSpinBox()
        self.amount_spin.setRange(0.01, 999999999.99)
        self.amount_spin.setPrefix("VND ")
        self.amount_spin.setDecimals(0)
        form.addRow("Số tiền *", self.amount_spin)

        self.method_combo = QComboBox()
        self.method_combo.addItems(["Cash", "Bank Transfer"])
        form.addRow("Hình thức thanh toán *", self.method_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setDate(QDate.currentDate())
        form.addRow("Ngày thu *", self.date_edit)

        self.period_combo = QComboBox()
        self.period_combo.addItem("", "")  # empty
        current_year = date.today().year
        for year in range(current_year - 1, current_year + 1):
            for month in range(1, 13):
                period = f"Tháng {month}/{year}"
                self.period_combo.addItem(period, period)
        form.addRow("Kỳ thanh toán", self.period_combo)

        self.received_by_edit = QLineEdit()
        current_user = get_current_user()
        if current_user:
            self.received_by_edit.setText(current_user.full_name)
        self.received_by_edit.setPlaceholderText("Người thu")
        form.addRow("Người thu", self.received_by_edit)

        self.note_edit = QLineEdit()
        self.note_edit.setPlaceholderText("Ghi chú (tùy chọn)")
        form.addRow("Ghi chú", self.note_edit)

        layout.addLayout(form)

        # ---- Buttons ----
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

        # Initial state
        self._on_source_changed(0)

    def _on_source_changed(self, index: int) -> None:
        is_student = (index == 0)  # "Từ học sinh"
        self.student_combo.setVisible(is_student)
        self.class_combo.setVisible(is_student)
        self.other_source_edit.setVisible(not is_student)
        if not is_student:
            self.student_combo.setCurrentIndex(-1)
            self.class_combo.setCurrentIndex(-1)
            self.other_source_edit.clear()
        else:
            self.other_source_edit.clear()

    def _load_students(self) -> None:
        try:
            students = self._student_service.list_students()
            self.student_combo.clear()
            for s in students:
                self.student_combo.addItem(f"{s.full_name} ({s.student_code})", s.id)
        except Exception as e:
            logger.exception("Error loading students")

    def _load_classes(self) -> None:
        try:
            classes = self._class_service.list_classes()
            self.class_combo.clear()
            for c in classes:
                self.class_combo.addItem(c.name, c.id)
        except Exception as e:
            logger.exception("Error loading classes")

    def _load_income(self) -> None:
        try:
            income = self._income_service.get_income(self._income_id)
            # Source
            if income.student_id is not None:
                self.source_combo.setCurrentIndex(0)  # "Từ học sinh"
                idx = self.student_combo.findData(income.student_id)
                if idx >= 0:
                    self.student_combo.setCurrentIndex(idx)
                idx2 = self.class_combo.findData(income.class_id)
                if idx2 >= 0:
                    self.class_combo.setCurrentIndex(idx2)
            else:
                self.source_combo.setCurrentIndex(1)  # "Nguồn khác"
                self.other_source_edit.setText(income.note or "")
            self._on_source_changed(self.source_combo.currentIndex())

            # Common fields
            idx3 = self.type_combo.findText(income.income_type)
            if idx3 >= 0:
                self.type_combo.setCurrentIndex(idx3)
            self.amount_spin.setValue(income.amount)
            idx4 = self.method_combo.findText(income.payment_method)
            if idx4 >= 0:
                self.method_combo.setCurrentIndex(idx4)
            qdate = QDate(income.payment_date.year, income.payment_date.month, income.payment_date.day)
            self.date_edit.setDate(qdate)
            if income.payment_period:
                idx5 = self.period_combo.findData(income.payment_period)
                if idx5 >= 0:
                    self.period_combo.setCurrentIndex(idx5)
                else:
                    self.period_combo.addItem(income.payment_period, income.payment_period)
                    self.period_combo.setCurrentIndex(self.period_combo.count() - 1)
            self.received_by_edit.setText(income.received_by or "")
            # For other source, note is used for description
            if income.student_id is None:
                self.note_edit.setText("")  # note will be saved as description
            else:
                self.note_edit.setText(income.note or "")
        except Exception as e:
            logger.exception("Error loading income")
            QMessageBox.critical(self, "Error", "Could not load income data.")
            self.reject()

    def _save(self) -> None:
        source_type = self.source_combo.currentText()
        if source_type == "Từ học sinh":
            student_id = self.student_combo.currentData()
            class_id = self.class_combo.currentData()
            note = self.note_edit.text().strip() or None
            if not student_id or not class_id:
                QMessageBox.warning(self, "Lỗi", "Vui lòng chọn học sinh và lớp học.")
                return
        else:  # "Nguồn khác"
            student_id = None
            class_id = None
            description = self.other_source_edit.text().strip()
            if not description:
                QMessageBox.warning(self, "Lỗi", "Vui lòng nhập mô tả nguồn thu.")
                return
            note = f"Nguồn khác: {description}"
            # Optionally, allow user to add extra note
            extra_note = self.note_edit.text().strip()
            if extra_note:
                note += f" ({extra_note})"

        income_type = self.type_combo.currentText()
        amount = self.amount_spin.value()
        payment_method = self.method_combo.currentText()
        payment_date = self.date_edit.date().toPython()
        payment_period = self.period_combo.currentData() or None
        received_by = self.received_by_edit.text().strip() or None

        try:
            if self._is_edit:
                self._income_service.update_income(
                    income_id=self._income_id,
                    amount=amount,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    payment_period=payment_period,
                    note=note,
                )
            else:
                self._income_service.create_income(
                    student_id=student_id,
                    class_id=class_id,
                    amount=amount,
                    income_type=income_type,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    payment_period=payment_period,
                    received_by=received_by,
                    note=note,
                )
            self.accept()
        except IncomeValidationError as e:
            QMessageBox.warning(self, "Lỗi xác thực", str(e))
        except Exception as e:
            logger.exception("Error saving income")
            QMessageBox.critical(self, "Lỗi", "Đã xảy ra lỗi không mong muốn.")