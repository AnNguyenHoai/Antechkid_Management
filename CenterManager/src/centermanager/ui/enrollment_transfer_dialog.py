# -*- coding: utf-8 -*-
"""Shared Enrollment transfer dialog used by Student and Class workspaces."""
from __future__ import annotations

from decimal import Decimal
from typing import Optional

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QLabel,
    QMessageBox,
    QPlainTextEdit,
    QVBoxLayout,
)

from centermanager.models.enrollment import Enrollment
from centermanager.services.enrollment_transfer_service import (
    EnrollmentTransferError,
    EnrollmentTransferService,
)


class EnrollmentTransferDialog(QDialog):
    """One UI contract for transferring an ACTIVE Enrollment to another class."""

    def __init__(
        self,
        transfer_service: EnrollmentTransferService,
        class_service,
        source_enrollment: Enrollment,
        *,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._transfer_service = transfer_service
        self._class_service = class_service
        self._source = source_enrollment
        self._preview: Optional[dict] = None

        self.setWindowTitle("Transfer student")
        self.setMinimumWidth(520)

        root = QVBoxLayout(self)
        form = QFormLayout()
        root.addLayout(form)

        self.source_label = QLabel(
            source_enrollment.class_name or f"Class #{source_enrollment.class_id}"
        )
        form.addRow("From class:", self.source_label)

        self.target_combo = QComboBox(self)
        self.target_combo.currentIndexChanged.connect(self._refresh_preview)
        form.addRow("To class:", self.target_combo)

        self.source_balance_label = QLabel("—")
        form.addRow("Current source balance:", self.source_balance_label)

        self.available_credit_label = QLabel("—")
        form.addRow("Available prepaid credit:", self.available_credit_label)

        self.target_fee_label = QLabel("—")
        form.addRow("Target tuition contract:", self.target_fee_label)

        self.credit_input = QDoubleSpinBox(self)
        self.credit_input.setDecimals(0)
        self.credit_input.setMinimum(0)
        self.credit_input.setMaximum(0)
        self.credit_input.setSingleStep(10000)
        self.credit_input.setSuffix(" VND")
        form.addRow("Credit to transfer:", self.credit_input)

        self.reason_input = QPlainTextEdit(self)
        self.reason_input.setPlaceholderText("Reason for transfer")
        self.reason_input.setMaximumHeight(100)
        form.addRow("Reason:", self.reason_input)

        self.error_label = QLabel("")
        self.error_label.setWordWrap(True)
        root.addWidget(self.error_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel
            | QDialogButtonBox.StandardButton.Ok,
            parent=self,
        )
        self.transfer_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.transfer_button.setText("Transfer")
        self.transfer_button.clicked.connect(self._submit)
        self.buttons.rejected.connect(self.reject)
        root.addWidget(self.buttons)

        self._load_targets()

    @staticmethod
    def _money_text(value) -> str:
        amount = Decimal(str(value or 0))
        return f"{amount:,.0f} VND"

    def _load_targets(self) -> None:
        self.target_combo.blockSignals(True)
        self.target_combo.clear()
        self.target_combo.addItem("Select target class", None)

        active_ids = {
            int(item.class_id)
            for item in self._class_service.get_student_enrollments(
                int(self._source.student_id)
            )
            if getattr(item, "status", None) == "ACTIVE"
            and getattr(item, "class_id", None) is not None
        }

        for class_obj in self._class_service.list_classes():
            if class_obj.id in active_ids:
                continue
            if getattr(class_obj, "status", "ACTIVE") != "ACTIVE":
                continue
            self.target_combo.addItem(
                f"{class_obj.name} — {class_obj.course or 'No course'}",
                int(class_obj.id),
            )

        self.target_combo.blockSignals(False)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        target_class_id = self.target_combo.currentData()
        self._preview = None
        self.error_label.clear()
        self.source_balance_label.setText("—")
        self.available_credit_label.setText("—")
        self.target_fee_label.setText("—")
        self.credit_input.setMaximum(0)
        self.credit_input.setValue(0)
        self.transfer_button.setEnabled(False)

        if target_class_id is None:
            return

        try:
            preview = self._transfer_service.preview(
                int(self._source.id),
                int(target_class_id),
            )
        except EnrollmentTransferError as exc:
            self.error_label.setText(str(exc))
            return
        except Exception as exc:
            self.error_label.setText(f"Transfer preview failed: {exc}")
            return

        self._preview = preview
        available = float(preview["available_prepaid_credit"])
        self.source_balance_label.setText(
            self._money_text(preview["source_balance"])
        )
        self.available_credit_label.setText(
            self._money_text(preview["available_prepaid_credit"])
        )
        self.target_fee_label.setText(
            f"{self._money_text(preview['agreed_course_fee'])} · "
            f"Sessions {preview['enrolled_from_session']}–"
            f"{preview['enrolled_until_session']}"
        )
        self.credit_input.setMaximum(available)
        self.credit_input.setValue(available)
        self.transfer_button.setEnabled(True)

    def _submit(self) -> None:
        target_class_id = self.target_combo.currentData()
        if target_class_id is None or self._preview is None:
            QMessageBox.warning(self, "Transfer", "Select a valid target class.")
            return

        reason = self.reason_input.toPlainText().strip()
        if not reason:
            QMessageBox.warning(
                self,
                "Transfer reason",
                "A transfer reason is required.",
            )
            return

        try:
            self._transfer_service.transfer(
                int(self._source.id),
                int(target_class_id),
                transferred_credit=self.credit_input.value(),
                reason=reason,
            )
        except EnrollmentTransferError as exc:
            QMessageBox.warning(self, "Transfer unavailable", str(exc))
            self._refresh_preview()
            return
        except Exception as exc:
            QMessageBox.critical(self, "Transfer failed", str(exc))
            return

        self.accept()


__all__ = ["EnrollmentTransferDialog"]
