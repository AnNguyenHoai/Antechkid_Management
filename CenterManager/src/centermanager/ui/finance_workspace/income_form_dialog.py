# -*- coding: utf-8 -*-
"""Create/edit Income dialog with immutable transaction identity in edit mode."""
import logging
from datetime import date
from typing import Optional

from PySide6.QtCore import QDate
from PySide6.QtWidgets import (
    QComboBox,
    QDateEdit,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from centermanager.core.clock import get_clock
from centermanager.core.current_user import get_current_user
from centermanager.core.wallet import WalletMappingError, resolve_wallet
from centermanager.services.class_service import ClassService
from centermanager.services.income_service import (
    IncomeService,
    IncomeValidationError,
)
from centermanager.services.student_service import StudentService
from centermanager.ui.design_system.components import AutoClearDoubleSpinBox

logger = logging.getLogger(__name__)


class IncomeFormDialog(QDialog):
    def __init__(
        self,
        income_service: IncomeService,
        student_service: StudentService,
        class_service: ClassService,
        income_id: Optional[int] = None,
        initial_payment_date: Optional[date] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._income_service = income_service
        self._student_service = student_service
        self._class_service = class_service
        self._income_id = income_id
        self._is_edit = income_id is not None
        self._initial_payment_date = initial_payment_date or get_clock().today()

        self.setWindowTitle("Sửa khoản thu" if self._is_edit else "Thêm khoản thu")
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
        form.setFieldGrowthPolicy(
            QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow
        )

        self.source_combo = QComboBox()
        self.source_combo.addItems(["Từ học sinh", "Nguồn khác"])
        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        form.addRow("Nguồn thu *", self.source_combo)

        self.student_combo = QComboBox()
        self._load_students()
        form.addRow("Học sinh *", self.student_combo)

        self.class_combo = QComboBox()
        self._load_classes()
        form.addRow("Lớp học *", self.class_combo)

        self.other_source_edit = QLineEdit()
        self.other_source_edit.setPlaceholderText(
            "Ví dụ: Tiền quyên góp, Lãi ngân hàng..."
        )
        self.other_source_edit.setVisible(False)
        form.addRow("Mô tả nguồn khác", self.other_source_edit)

        self.type_combo = QComboBox()
        for value in ["Tuition", "Book", "Robot Kit", "Material", "Other"]:
            self.type_combo.addItem(value)
        self.type_combo.currentTextChanged.connect(self._on_income_type_changed)
        form.addRow("Loại thu *", self.type_combo)

        self.amount_spin = AutoClearDoubleSpinBox(prefix="VND ")
        self.amount_spin.setRange(0.01, 999999999.99)
        form.addRow("Số tiền *", self.amount_spin)

        self.method_combo = QComboBox()
        self.method_combo.addItem("Cash", "CASH")
        self.method_combo.addItem("Bank", "BANK")
        form.addRow("Wallet *", self.method_combo)

        self.date_edit = QDateEdit()
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        initial = self._initial_payment_date
        self.date_edit.setDate(QDate(initial.year, initial.month, initial.day))
        form.addRow("Ngày thu *", self.date_edit)

        # Legacy display metadata only. Canonical Finance period is always
        # resolved by IncomeService from payment_date.
        self.period_combo = QComboBox()
        self.period_combo.addItem("", "")
        current_year = get_clock().today().year
        for year in range(current_year - 1, current_year + 1):
            for month in range(1, 13):
                period = f"Tháng {month}/{year}"
                self.period_combo.addItem(period, period)
        form.addRow("Kỳ thanh toán (ghi chú)", self.period_combo)

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

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()
        self.save_btn = QPushButton("Lưu")
        self.save_btn.setFixedWidth(100)
        self.cancel_btn = QPushButton("Hủy")
        self.cancel_btn.setFixedWidth(100)
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        self.save_btn.clicked.connect(self._save)
        self.cancel_btn.clicked.connect(self.reject)
        self._on_source_changed(0)

    def _on_source_changed(self, index: int) -> None:
        is_student = index == 0
        self.student_combo.setVisible(is_student)
        self.class_combo.setVisible(is_student)
        self.other_source_edit.setVisible(not is_student)

        if self._is_edit:
            return
        if is_student:
            self.type_combo.setEnabled(True)
            if self.type_combo.currentText() == "Other":
                self.type_combo.setCurrentText("Tuition")
        else:
            self.type_combo.setCurrentText("Other")
            self.type_combo.setEnabled(False)

    def _on_income_type_changed(self, income_type: str) -> None:
        """Keep the source selector consistent with Income ownership rules."""
        if self._is_edit:
            return
        if income_type == "Other":
            if self.source_combo.currentIndex() != 1:
                self.source_combo.setCurrentIndex(1)
        elif self.source_combo.currentIndex() != 0:
            self.source_combo.setCurrentIndex(0)

    def _load_students(self) -> None:
        try:
            students = self._student_service.list_students()
            self.student_combo.clear()
            for student in students:
                self.student_combo.addItem(
                    f"{student.full_name} ({student.student_code})",
                    student.id,
                )
        except Exception:
            logger.exception("Error loading students")

    def _load_classes(self) -> None:
        try:
            classes = self._class_service.list_classes()
            self.class_combo.clear()
            for class_obj in classes:
                self.class_combo.addItem(class_obj.name, class_obj.id)
        except Exception:
            logger.exception("Error loading classes")

    def _lock_identity_fields(self) -> None:
        self.source_combo.setEnabled(False)
        self.student_combo.setEnabled(False)
        self.class_combo.setEnabled(False)
        self.type_combo.setEnabled(False)
        self.other_source_edit.setEnabled(False)

    def _load_income(self) -> None:
        try:
            income = self._income_service.get_income(self._income_id)
            if income.student_id is not None:
                self.source_combo.setCurrentIndex(0)
                student_index = self.student_combo.findData(income.student_id)
                if student_index >= 0:
                    self.student_combo.setCurrentIndex(student_index)
                class_index = self.class_combo.findData(income.class_id)
                if class_index >= 0:
                    self.class_combo.setCurrentIndex(class_index)
            else:
                self.source_combo.setCurrentIndex(1)
                self.other_source_edit.setText(income.note or "")

            type_index = self.type_combo.findText(income.income_type)
            if type_index >= 0:
                self.type_combo.setCurrentIndex(type_index)
            self.amount_spin.setValue(income.amount)

            try:
                wallet = resolve_wallet(income.payment_method).value
                method_index = self.method_combo.findData(wallet)
            except WalletMappingError:
                self.method_combo.addItem(
                    f"Legacy value requires selection: {income.payment_method}",
                    None,
                )
                method_index = self.method_combo.count() - 1
            if method_index >= 0:
                self.method_combo.setCurrentIndex(method_index)

            self.date_edit.setDate(
                QDate(
                    income.payment_date.year,
                    income.payment_date.month,
                    income.payment_date.day,
                )
            )
            if income.payment_period:
                period_index = self.period_combo.findData(income.payment_period)
                if period_index < 0:
                    self.period_combo.addItem(
                        income.payment_period, income.payment_period
                    )
                    period_index = self.period_combo.count() - 1
                self.period_combo.setCurrentIndex(period_index)

            self.received_by_edit.setText(income.received_by or "")
            self.note_edit.setText(income.note or "")
            self._on_source_changed(self.source_combo.currentIndex())
            self._lock_identity_fields()
        except Exception as exc:
            logger.exception("Error loading income %s for edit", self._income_id)
            QMessageBox.critical(
                self,
                "Lỗi",
                f"Không thể tải dữ liệu thu nhập: {exc}",
            )
            self.reject()

    def _create_identity_payload(self):
        source_type = self.source_combo.currentText()
        if source_type == "Từ học sinh":
            student_id = self.student_combo.currentData()
            class_id = self.class_combo.currentData()
            if not student_id or not class_id:
                raise IncomeValidationError(
                    "Vui lòng chọn học sinh và lớp học."
                )
            note = self.note_edit.text().strip() or None
            return student_id, class_id, self.type_combo.currentText(), note

        description = self.other_source_edit.text().strip()
        if not description:
            raise IncomeValidationError("Vui lòng nhập mô tả nguồn thu.")
        note = f"Nguồn khác: {description}"
        extra_note = self.note_edit.text().strip()
        if extra_note:
            note += f" ({extra_note})"
        return None, None, "Other", note

    def _save(self) -> None:
        amount = self.amount_spin.value()
        if amount <= 0:
            QMessageBox.warning(
                self, "Lỗi", "Số tiền phải lớn hơn 0."
            )
            return

        payment_method = self.method_combo.currentData()
        if payment_method is None:
            QMessageBox.warning(
                self,
                "Wallet required",
                "Select CASH or BANK before saving this transaction.",
            )
            return
        payment_date = self.date_edit.date().toPython()
        payment_period = self.period_combo.currentData()
        received_by = self.received_by_edit.text().strip()
        note = self.note_edit.text().strip()

        try:
            if self._is_edit:
                self._income_service.update_income(
                    income_id=self._income_id,
                    amount=amount,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    payment_period=payment_period,
                    received_by=received_by,
                    note=note,
                )
            else:
                student_id, class_id, income_type, create_note = (
                    self._create_identity_payload()
                )
                self._income_service.create_income(
                    student_id=student_id,
                    class_id=class_id,
                    amount=amount,
                    income_type=income_type,
                    payment_method=payment_method,
                    payment_date=payment_date,
                    payment_period=payment_period or None,
                    received_by=received_by or None,
                    note=create_note,
                )
            self.accept()
        except IncomeValidationError as exc:
            QMessageBox.warning(self, "Lỗi xác thực", str(exc))
        except Exception:
            logger.exception("Error saving income")
            QMessageBox.critical(
                self, "Lỗi", "Đã xảy ra lỗi không mong muốn."
            )
