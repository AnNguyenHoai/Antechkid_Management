# -*- coding: utf-8 -*-
"""Enrollment pricing preview/override dialog for mid-course joins."""
from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
)

from centermanager.core.capabilities import Capability
from centermanager.core.current_user import get_current_user
from centermanager.services.authorization_service import AuthorizationService
from centermanager.services.enrollment_service import EnrollmentValidationError
from centermanager.ui.design_system.tokens import SPACING


class EnrollmentPricingDialog(QDialog):
    """Shows deterministic remaining-session pricing before an enrollment save."""

    def __init__(self, enrollment_service, class_id: int, parent=None) -> None:
        super().__init__(parent)
        self._service = enrollment_service
        self._class_id = int(class_id)
        self._preview = None
        self.setWindowTitle("Enrollment tuition terms")
        self.setMinimumWidth(460)
        self._build_ui()
        self._load_default_preview()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"])
        layout.setSpacing(SPACING["md"])

        form = QFormLayout()
        self.start_session = QSpinBox(self)
        self.start_session.setMinimum(1)
        self.start_session.valueChanged.connect(self._reload_preview)
        form.addRow("Start from session", self.start_session)

        self.session_range = QLabel("—", self)
        form.addRow("Effective range", self.session_range)
        self.remaining_sessions = QLabel("—", self)
        form.addRow("Contracted sessions", self.remaining_sessions)
        self.unit_fee = QLabel("—", self)
        form.addRow("Unit fee", self.unit_fee)
        self.suggested_fee = QLabel("—", self)
        form.addRow("Suggested agreed fee", self.suggested_fee)
        layout.addLayout(form)

        self.override_enabled = QCheckBox("Override suggested agreed fee", self)
        self.override_enabled.setVisible(
            AuthorizationService.allows(
                get_current_user(),
                Capability.TUITION_ENROLLMENT_OVERRIDE,
            )
        )
        self.override_enabled.toggled.connect(self._update_override_state)
        layout.addWidget(self.override_enabled)

        override_form = QFormLayout()
        self.override_fee = QLineEdit(self)
        self.override_fee.setPlaceholderText("Enter agreed fee")
        override_form.addRow("Override fee", self.override_fee)
        self.override_reason = QLineEdit(self)
        self.override_reason.setPlaceholderText("Required reason")
        override_form.addRow("Reason", self.override_reason)
        layout.addLayout(override_form)
        self._update_override_state(False)

        self.error_label = QLabel("", self)
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok,
            parent=self,
        )
        self.buttons.accepted.connect(self._accept_if_valid)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

    @staticmethod
    def _money_text(value) -> str:
        amount = Decimal(value)
        return f"{amount:,.0f}"

    def _load_default_preview(self) -> None:
        try:
            preview = self._service.preview_enrollment_pricing(self._class_id)
            self.start_session.blockSignals(True)
            self.start_session.setMaximum(preview["class_planned_sessions"])
            self.start_session.setValue(preview["enrolled_from_session"])
            self.start_session.blockSignals(False)
            self._apply_preview(preview)
        except Exception as exc:
            self.error_label.setText(str(exc))
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _reload_preview(self) -> None:
        try:
            preview = self._service.preview_enrollment_pricing(
                self._class_id,
                enrolled_from_session=self.start_session.value(),
            )
            self._apply_preview(preview)
        except Exception as exc:
            self._preview = None
            self.error_label.setText(str(exc))
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _apply_preview(self, preview: dict) -> None:
        self._preview = preview
        self.error_label.setText("")
        self.session_range.setText(
            f"#{preview['enrolled_from_session']} → #{preview['enrolled_until_session']}"
        )
        self.remaining_sessions.setText(str(preview["planned_sessions"]))
        self.unit_fee.setText(self._money_text(preview["unit_fee"]))
        self.suggested_fee.setText(self._money_text(preview["suggested_agreed_course_fee"]))
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(True)

    def _update_override_state(self, enabled: bool) -> None:
        self.override_fee.setEnabled(enabled)
        self.override_reason.setEnabled(enabled)
        if not enabled:
            self.override_fee.clear()
            self.override_reason.clear()

    def _accept_if_valid(self) -> None:
        if self._preview is None:
            return
        if self.override_enabled.isChecked():
            try:
                override = Decimal(self.override_fee.text().replace(",", "").strip())
            except Exception:
                self.error_label.setText("Override fee must be a valid number.")
                return
            if override < 0:
                self.error_label.setText("Override fee cannot be negative.")
                return
            if not self.override_reason.text().strip():
                self.error_label.setText("A reason is required for a fee override.")
                return
        self.accept()

    def enrollment_kwargs(self) -> dict:
        if self._preview is None:
            raise EnrollmentValidationError("Enrollment pricing is unavailable.")
        result = {
            "enrolled_from_session": self._preview["enrolled_from_session"],
            "enrolled_until_session": self._preview["enrolled_until_session"],
        }
        if self.override_enabled.isChecked():
            result["agreed_course_fee_override"] = Decimal(
                self.override_fee.text().replace(",", "").strip()
            )
            result["override_reason"] = self.override_reason.text().strip()
        return result
