# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QLabel,
    QDoubleSpinBox,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QMessageBox,
    QGroupBox,
)


class FinancialSettlementPage(QWidget):
    """FinancePeriod reconciliation UI driven by the workspace shared period."""

    def __init__(self, settlement_service, notification_service=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._settlement_service = settlement_service
        self._notification_service = notification_service
        self._write_enabled = False
        self._loaded_status = "DRAFT"
        self._target_date = date.today()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(14)

        # The FinanceWorkspaceShell owns period navigation. This row only shows
        # the exact canonical period resolved by the Settlement service.
        period_row = QHBoxLayout()
        period_row.addWidget(QLabel("Settlement period:"))
        self.period_label = QLabel("")
        self.period_label.setStyleSheet("font-weight: 600;")
        period_row.addWidget(self.period_label)
        period_row.addStretch()
        self.status_label = QLabel("DRAFT")
        self.status_label.setStyleSheet("font-weight: 700;")
        period_row.addWidget(self.status_label)
        layout.addLayout(period_row)

        group = QGroupBox("Financial Settlement")
        grid = QGridLayout(group)
        grid.addWidget(QLabel(""), 0, 0)
        grid.addWidget(QLabel("Cash"), 0, 1)
        grid.addWidget(QLabel("Bank"), 0, 2)

        grid.addWidget(QLabel("Opening balance"), 1, 0)
        self.opening_cash = self._money_spin()
        self.opening_bank = self._money_spin()
        grid.addWidget(self.opening_cash, 1, 1)
        grid.addWidget(self.opening_bank, 1, 2)

        grid.addWidget(QLabel("System income"), 2, 0)
        self.income_cash = QLabel("0")
        self.income_bank = QLabel("0")
        grid.addWidget(self.income_cash, 2, 1)
        grid.addWidget(self.income_bank, 2, 2)

        grid.addWidget(QLabel("System expense"), 3, 0)
        self.expense_cash = QLabel("0")
        self.expense_bank = QLabel("0")
        grid.addWidget(self.expense_cash, 3, 1)
        grid.addWidget(self.expense_bank, 3, 2)

        grid.addWidget(QLabel("Expected closing"), 4, 0)
        self.expected_cash = QLabel("0")
        self.expected_bank = QLabel("0")
        grid.addWidget(self.expected_cash, 4, 1)
        grid.addWidget(self.expected_bank, 4, 2)

        grid.addWidget(QLabel("Actual closing"), 5, 0)
        self.actual_cash = QLineEdit()
        self.actual_bank = QLineEdit()
        self.actual_cash.setPlaceholderText("Enter actual cash")
        self.actual_bank.setPlaceholderText("Enter actual bank balance")
        grid.addWidget(self.actual_cash, 5, 1)
        grid.addWidget(self.actual_bank, 5, 2)

        grid.addWidget(QLabel("Difference"), 6, 0)
        self.difference_cash = QLabel("-")
        self.difference_bank = QLabel("-")
        grid.addWidget(self.difference_cash, 6, 1)
        grid.addWidget(self.difference_bank, 6, 2)
        layout.addWidget(group)

        layout.addWidget(QLabel("Comment / reconciliation note"))
        self.comment_edit = QPlainTextEdit()
        self.comment_edit.setMaximumHeight(90)
        layout.addWidget(self.comment_edit)

        buttons = QHBoxLayout()
        buttons.addStretch()
        self.save_btn = QPushButton("Save Draft")
        self.confirm_btn = QPushButton("Confirm Settlement")
        self.save_btn.clicked.connect(self._save_draft)
        self.confirm_btn.clicked.connect(self._confirm)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.confirm_btn)
        layout.addLayout(buttons)
        layout.addStretch()
        self._apply_write_state()

    @staticmethod
    def _money_spin() -> QDoubleSpinBox:
        spin = QDoubleSpinBox()
        spin.setDecimals(2)
        spin.setRange(-999999999999.99, 999999999999.99)
        spin.setSingleStep(100000.0)
        spin.setSuffix(" VND")
        return spin

    @staticmethod
    def _format_money(value) -> str:
        if value is None:
            return "-"
        return f"{Decimal(str(value)):,.2f} VND"

    @staticmethod
    def _optional_text_money(edit: QLineEdit):
        text = edit.text().strip().replace(",", "")
        if not text:
            return None
        try:
            return Decimal(text)
        except InvalidOperation as exc:
            raise ValueError("Actual closing balances must be valid numbers.") from exc

    @staticmethod
    def _set_optional_money(edit: QLineEdit, value) -> None:
        edit.setText("" if value is None else f"{Decimal(str(value)):.2f}")

    def _notify(self, message: str, level: str = "warning") -> None:
        if self._notification_service is not None and hasattr(self._notification_service, "notify"):
            self._notification_service.notify(message, level)
        else:
            QMessageBox.warning(self, "Financial Settlement", message)

    def refresh(
        self,
        *_args,
        target_date: Optional[date] = None,
        period_start=None,
        period_end=None,
        period_configured=None,
        **_kwargs,
    ) -> None:
        del period_start, period_end
        if target_date is not None:
            self._target_date = target_date
        if period_configured is False:
            self.period_label.setText("Finance period not configured")
            self._loaded_status = "UNAVAILABLE"
            self.status_label.setText("UNAVAILABLE")
            self._apply_write_state()
            return
        if self._settlement_service is None:
            self.period_label.setText("Settlement service unavailable")
            self._loaded_status = "UNAVAILABLE"
            self.status_label.setText("UNAVAILABLE")
            self._apply_write_state()
            return
        try:
            data = self._settlement_service.get_preview(target_date=self._target_date)
        except Exception as exc:
            self.period_label.setText(str(exc))
            self._loaded_status = "UNAVAILABLE"
            self.status_label.setText("UNAVAILABLE")
            self._apply_write_state()
            return

        self.period_label.setText(data["period_label"])
        self._loaded_status = data["status"]
        self.status_label.setText(data["status"])
        if data.get("confirmed_at") is not None:
            self.status_label.setToolTip(f"Confirmed: {data['confirmed_at']}")
        else:
            self.status_label.setToolTip("")

        self.opening_cash.setValue(float(data["opening_cash"]))
        self.opening_bank.setValue(float(data["opening_bank"]))
        self.income_cash.setText(self._format_money(data["income_cash"]))
        self.income_bank.setText(self._format_money(data["income_bank"]))
        self.expense_cash.setText(self._format_money(data["expense_cash"]))
        self.expense_bank.setText(self._format_money(data["expense_bank"]))
        self.expected_cash.setText(self._format_money(data["expected_closing_cash"]))
        self.expected_bank.setText(self._format_money(data["expected_closing_bank"]))
        self._set_optional_money(self.actual_cash, data["actual_closing_cash"])
        self._set_optional_money(self.actual_bank, data["actual_closing_bank"])
        self.difference_cash.setText(self._format_money(data["difference_cash"]))
        self.difference_bank.setText(self._format_money(data["difference_bank"]))
        self.comment_edit.setPlainText(data.get("comment", ""))
        self._apply_write_state()

    def _request_payload(self) -> dict:
        return {
            "target_date": self._target_date,
            "opening_cash": Decimal(str(self.opening_cash.value())),
            "opening_bank": Decimal(str(self.opening_bank.value())),
            "actual_closing_cash": self._optional_text_money(self.actual_cash),
            "actual_closing_bank": self._optional_text_money(self.actual_bank),
            "comment": self.comment_edit.toPlainText(),
        }

    def _save_draft(self) -> None:
        try:
            self._settlement_service.save_draft(**self._request_payload())
            self.refresh()
        except Exception as exc:
            self._notify(str(exc))

    def _confirm(self) -> None:
        try:
            payload = self._request_payload()
            if payload["actual_closing_cash"] is None or payload["actual_closing_bank"] is None:
                raise ValueError("Enter both actual closing balances before confirmation.")
            answer = QMessageBox.question(
                self,
                "Confirm Settlement",
                "Confirm this FinancePeriod settlement? Confirmed settlements cannot be edited.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._settlement_service.confirm(**payload)
            self.refresh()
        except Exception as exc:
            self._notify(str(exc))

    def _apply_write_state(self) -> None:
        editable = self._write_enabled and self._loaded_status == "DRAFT"
        for widget in (
            self.opening_cash,
            self.opening_bank,
            self.actual_cash,
            self.actual_bank,
            self.comment_edit,
        ):
            widget.setEnabled(editable)
        self.save_btn.setEnabled(editable)
        self.confirm_btn.setEnabled(editable)

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self._apply_write_state()
