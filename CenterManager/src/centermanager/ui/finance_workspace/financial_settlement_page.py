# -*- coding: utf-8 -*-
from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Optional

from PySide6.QtCore import QRegularExpression, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from centermanager.core.capabilities import Capability
from centermanager.core.clock import get_clock
from centermanager.ui.design_system.tokens import (
    COLORS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)
from centermanager.ui.finance_workspace.action_state import can_mutate, has_capability


def _format_vnd(value) -> str:
    """Format persisted Decimal-compatible money without changing its precision."""
    if value is None:
        return "-"
    amount = Decimal(str(value))
    if amount == amount.to_integral_value():
        return f"{amount:,.0f} ₫"
    return f"{amount:,.2f} ₫"


class MoneyLineEdit(QLineEdit):
    """Numeric-only VND editor with grouped display and Decimal output."""

    def __init__(
        self,
        *,
        optional: bool,
        placeholder: str = "0 ₫",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._optional = optional
        self.setPlaceholderText(placeholder)
        self.setAlignment(
            self.alignment()
            | self.alignment().AlignRight
        )
        # Allows digits, optional leading minus sign, grouping separators and
        # at most two decimal places. Currency symbol is presentation-only.
        pattern = QRegularExpression(r"^-?[0-9,]*(?:\.[0-9]{0,2})?$")
        self.setValidator(QRegularExpressionValidator(pattern, self))
        self.editingFinished.connect(self._normalize_display)

    @staticmethod
    def _parse(text: str) -> Optional[Decimal]:
        normalized = (
            (text or "")
            .replace(",", "")
            .replace("₫", "")
            .replace("VND", "")
            .strip()
        )
        if not normalized:
            return None
        try:
            return Decimal(normalized)
        except InvalidOperation as exc:
            raise ValueError("Settlement balances must be valid numbers.") from exc

    def money_value(self) -> Optional[Decimal]:
        value = self._parse(self.text())
        if value is None and not self._optional:
            return Decimal("0")
        return value

    def set_money_value(self, value) -> None:
        if value is None:
            self.clear()
            return
        self.setText(_format_vnd(value))

    def focusInEvent(self, event) -> None:  # noqa: N802
        value = self._parse(self.text())
        if value is not None:
            editable = (
                f"{value:,.0f}"
                if value == value.to_integral_value()
                else f"{value:,.2f}"
            )
            self.setText(editable)
        super().focusInEvent(event)

    def _normalize_display(self) -> None:
        value = self._parse(self.text())
        if value is None:
            if not self._optional:
                self.setText(_format_vnd(Decimal("0")))
            return
        self.setText(_format_vnd(value))


class FinancialSettlementPage(QWidget):
    """FinancePeriod reconciliation UI driven by the workspace shared period."""

    settlement_changed = Signal()

    def __init__(self, settlement_service, notification_service=None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._settlement_service = settlement_service
        self._notification_service = notification_service
        self._write_enabled = False
        self._loaded_status = "DRAFT"
        self._loaded_id = None
        self._target_date = get_clock().today()
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["xl"])
        layout.setSpacing(SPACING["lg"])

        header = QFrame(self)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACING["sm"])

        title_block = QVBoxLayout()
        title_block.setSpacing(SPACING["xs"])
        title = QLabel("Financial Settlement", self)
        title.setStyleSheet(
            f"font-family:{FONT_FAMILY}; font-size:{TYPOGRAPHY['page_title']}px; "
            f"font-weight:{FONT_WEIGHTS['semibold']}; color:{COLORS['text_primary']};"
        )
        title_block.addWidget(title)

        period_row = QHBoxLayout()
        period_caption = QLabel("Settlement period:", self)
        period_caption.setStyleSheet(
            f"font-size:{TYPOGRAPHY['body']}px; color:{COLORS['text_muted']};"
        )
        period_row.addWidget(period_caption)
        self.period_label = QLabel("", self)
        self.period_label.setStyleSheet(
            f"font-size:{TYPOGRAPHY['body']}px; font-weight:{FONT_WEIGHTS['semibold']}; "
            f"color:{COLORS['text_primary']};"
        )
        period_row.addWidget(self.period_label)
        period_row.addStretch()
        title_block.addLayout(period_row)
        header_layout.addLayout(title_block, 1)

        self.status_label = QLabel("DRAFT", self)
        self.status_label.setAlignment(self.status_label.alignment().AlignCenter)
        self.status_label.setMinimumWidth(120)
        self.status_label.setStyleSheet(
            f"padding:{SPACING['sm']}px {SPACING['md']}px; "
            f"font-size:{TYPOGRAPHY['body']}px; font-weight:{FONT_WEIGHTS['bold']}; "
            f"background:{COLORS['state_warning_bg']}; color:{COLORS['state_warning']}; "
            f"border-radius:{RADIUS['pill']}px;"
        )
        header_layout.addWidget(self.status_label)
        layout.addWidget(header)

        group = QGroupBox("Reconciliation", self)
        group.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        group.setMinimumWidth(820)
        group.setStyleSheet(
            f"""
            QGroupBox {{
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['section_title']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
                color: {COLORS['text_primary']};
                border: 1px solid {COLORS['border_default']};
                border-radius: {RADIUS['lg']}px;
                margin-top: {SPACING['md']}px;
                padding-top: {SPACING['md']}px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: {SPACING['md']}px;
                padding: 0 {SPACING['xs']}px;
            }}
            """
        )
        grid = QGridLayout(group)
        grid.setContentsMargins(SPACING["lg"], SPACING["xl"], SPACING["lg"], SPACING["lg"])
        grid.setHorizontalSpacing(SPACING["xl"])
        grid.setVerticalSpacing(SPACING["md"])
        grid.setColumnStretch(0, 2)
        grid.setColumnStretch(1, 3)
        grid.setColumnStretch(2, 3)

        grid.addWidget(self._column_header(""), 0, 0)
        grid.addWidget(self._column_header("Cash"), 0, 1)
        grid.addWidget(self._column_header("Bank"), 0, 2)

        grid.addWidget(self._row_label("Opening balance"), 1, 0)
        self.opening_cash = self._money_input(optional=False)
        self.opening_bank = self._money_input(optional=False)
        grid.addWidget(self.opening_cash, 1, 1)
        grid.addWidget(self.opening_bank, 1, 2)

        grid.addWidget(self._row_label("System income"), 2, 0)
        self.income_cash = self._money_label()
        self.income_bank = self._money_label()
        grid.addWidget(self.income_cash, 2, 1)
        grid.addWidget(self.income_bank, 2, 2)

        grid.addWidget(self._row_label("System expense"), 3, 0)
        self.expense_cash = self._money_label()
        self.expense_bank = self._money_label()
        grid.addWidget(self.expense_cash, 3, 1)
        grid.addWidget(self.expense_bank, 3, 2)

        grid.addWidget(self._row_label("Expected closing", strong=True), 4, 0)
        self.expected_cash = self._money_label(strong=True)
        self.expected_bank = self._money_label(strong=True)
        grid.addWidget(self.expected_cash, 4, 1)
        grid.addWidget(self.expected_bank, 4, 2)

        separator = QFrame(group)
        separator.setFrameShape(QFrame.Shape.HLine)
        separator.setStyleSheet(f"color:{COLORS['border_default']};")
        grid.addWidget(separator, 5, 0, 1, 3)

        grid.addWidget(self._row_label("Actual closing", strong=True), 6, 0)
        self.actual_cash = self._money_input(optional=True)
        self.actual_bank = self._money_input(optional=True)
        grid.addWidget(self.actual_cash, 6, 1)
        grid.addWidget(self.actual_bank, 6, 2)

        grid.addWidget(self._row_label("Difference", strong=True), 7, 0)
        self.difference_cash = self._money_label(strong=True)
        self.difference_bank = self._money_label(strong=True)
        grid.addWidget(self.difference_cash, 7, 1)
        grid.addWidget(self.difference_bank, 7, 2)
        layout.addWidget(group)

        note_label = QLabel("Comment / reconciliation note", self)
        note_label.setStyleSheet(
            f"font-size:{TYPOGRAPHY['body']}px; font-weight:{FONT_WEIGHTS['semibold']}; "
            f"color:{COLORS['text_primary']};"
        )
        layout.addWidget(note_label)

        self.comment_edit = QPlainTextEdit(self)
        self.comment_edit.setMinimumHeight(120)
        self.comment_edit.setMaximumHeight(180)
        self.comment_edit.setPlaceholderText(
            "Add a reconciliation note. A comment is required when actual and expected balances differ."
        )
        self.comment_edit.setStyleSheet(
            f"font-family:{FONT_FAMILY}; font-size:{TYPOGRAPHY['body']}px; "
            f"padding:{SPACING['sm']}px;"
        )
        layout.addWidget(self.comment_edit)

        buttons = QHBoxLayout()
        buttons.setSpacing(SPACING["sm"])
        buttons.addStretch()
        self.save_btn = QPushButton("Save Draft", self)
        self.confirm_btn = QPushButton("Confirm Settlement", self)
        self.reopen_btn = QPushButton("Reopen Settlement", self)
        for button in (self.save_btn, self.confirm_btn, self.reopen_btn):
            button.setMinimumHeight(40)
            button.setStyleSheet(
                f"font-size:{TYPOGRAPHY['body']}px; padding:0 {SPACING['lg']}px;"
            )
        self.save_btn.clicked.connect(self._save_draft)
        self.confirm_btn.clicked.connect(self._confirm)
        self.reopen_btn.clicked.connect(self._reopen)
        buttons.addWidget(self.save_btn)
        buttons.addWidget(self.confirm_btn)
        buttons.addWidget(self.reopen_btn)
        layout.addLayout(buttons)
        layout.addStretch(1)
        self._apply_write_state()

    @staticmethod
    def _column_header(text: str) -> QLabel:
        label = QLabel(text)
        label.setAlignment(label.alignment().AlignRight)
        label.setStyleSheet(
            f"font-family:{FONT_FAMILY}; font-size:{TYPOGRAPHY['body']}px; "
            f"font-weight:{FONT_WEIGHTS['bold']}; color:{COLORS['text_secondary']};"
        )
        return label

    @staticmethod
    def _row_label(text: str, *, strong: bool = False) -> QLabel:
        label = QLabel(text)
        weight = FONT_WEIGHTS["semibold"] if strong else FONT_WEIGHTS["medium"]
        size = TYPOGRAPHY["body"] + (1 if strong else 0)
        label.setStyleSheet(
            f"font-family:{FONT_FAMILY}; font-size:{size}px; "
            f"font-weight:{weight}; color:{COLORS['text_primary']};"
        )
        return label

    @staticmethod
    def _money_input(*, optional: bool) -> MoneyLineEdit:
        edit = MoneyLineEdit(optional=optional)
        edit.setMinimumHeight(42)
        edit.setMinimumWidth(220)
        edit.setStyleSheet(
            f"font-family:{FONT_FAMILY}; font-size:{TYPOGRAPHY['body'] + 1}px; "
            f"padding:0 {SPACING['sm']}px;"
        )
        if not optional:
            edit.set_money_value(Decimal("0"))
        return edit

    @staticmethod
    def _money_label(*, strong: bool = False) -> QLabel:
        label = QLabel("0 ₫")
        label.setAlignment(label.alignment().AlignRight | label.alignment().AlignVCenter)
        size = TYPOGRAPHY["body"] + (2 if strong else 1)
        weight = FONT_WEIGHTS["semibold"] if strong else FONT_WEIGHTS["medium"]
        label.setMinimumHeight(38)
        label.setStyleSheet(
            f"font-family:{FONT_FAMILY}; font-size:{size}px; "
            f"font-weight:{weight}; color:{COLORS['text_primary']};"
        )
        return label

    @staticmethod
    def _format_money(value) -> str:
        return _format_vnd(value)

    @staticmethod
    def _optional_text_money(edit: MoneyLineEdit):
        return edit.money_value()

    @staticmethod
    def _set_optional_money(edit: MoneyLineEdit, value) -> None:
        edit.set_money_value(value)

    def _set_difference(self, label: QLabel, value) -> None:
        label.setText(self._format_money(value))
        if value is None:
            color = COLORS["text_muted"]
        elif Decimal(str(value)) == Decimal("0"):
            color = COLORS["state_success"]
        else:
            color = COLORS["state_danger"]
        label.setStyleSheet(
            f"font-family:{FONT_FAMILY}; font-size:{TYPOGRAPHY['body'] + 2}px; "
            f"font-weight:{FONT_WEIGHTS['semibold']}; color:{color};"
        )

    def _notify(self, message: str, level: str = "warning") -> None:
        if self._notification_service is not None and hasattr(self._notification_service, "notify"):
            self._notification_service.notify(message, level)
        else:
            QMessageBox.warning(self, "Financial Settlement", message)

    def _clear_projection(self, message: str) -> None:
        self.period_label.setText(message)
        self._loaded_status = "UNAVAILABLE"
        self._loaded_id = None
        self.status_label.setText("UNAVAILABLE")
        for label in (
            self.income_cash,
            self.income_bank,
            self.expense_cash,
            self.expense_bank,
            self.expected_cash,
            self.expected_bank,
            self.difference_cash,
            self.difference_bank,
        ):
            label.setText("-")
        self.opening_cash.set_money_value(Decimal("0"))
        self.opening_bank.set_money_value(Decimal("0"))
        self.actual_cash.clear()
        self.actual_bank.clear()
        self.comment_edit.clear()
        self._apply_write_state()

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
            self._clear_projection("Finance period not configured")
            return
        if self._settlement_service is None:
            self._clear_projection("Settlement service unavailable")
            return
        if not has_capability(Capability.FINANCE_SETTLEMENT_VIEW):
            self._clear_projection("Settlement access restricted")
            return
        try:
            data = self._settlement_service.get_preview(target_date=self._target_date)
        except Exception as exc:
            self._clear_projection(str(exc))
            return

        self.period_label.setText(data["period_label"])
        self._loaded_status = data["status"]
        self._loaded_id = data.get("id")
        self.status_label.setText(data["status"])
        if data.get("confirmed_at") is not None:
            self.status_label.setToolTip(f"Confirmed: {data['confirmed_at']}")
        else:
            self.status_label.setToolTip("")

        self.opening_cash.set_money_value(data["opening_cash"])
        self.opening_bank.set_money_value(data["opening_bank"])
        self.income_cash.setText(self._format_money(data["income_cash"]))
        self.income_bank.setText(self._format_money(data["income_bank"]))
        self.expense_cash.setText(self._format_money(data["expense_cash"]))
        self.expense_bank.setText(self._format_money(data["expense_bank"]))
        self.expected_cash.setText(self._format_money(data["expected_closing_cash"]))
        self.expected_bank.setText(self._format_money(data["expected_closing_bank"]))
        self._set_optional_money(self.actual_cash, data["actual_closing_cash"])
        self._set_optional_money(self.actual_bank, data["actual_closing_bank"])
        self._set_difference(self.difference_cash, data["difference_cash"])
        self._set_difference(self.difference_bank, data["difference_bank"])
        self.comment_edit.setPlainText(data.get("comment", ""))
        self._apply_write_state()

    def _request_payload(self) -> dict:
        return {
            "target_date": self._target_date,
            "opening_cash": self.opening_cash.money_value() or Decimal("0"),
            "opening_bank": self.opening_bank.money_value() or Decimal("0"),
            "actual_closing_cash": self._optional_text_money(self.actual_cash),
            "actual_closing_bank": self._optional_text_money(self.actual_bank),
            "comment": self.comment_edit.toPlainText(),
        }

    def _save_draft(self) -> None:
        try:
            self._settlement_service.save_draft(**self._request_payload())
            self.settlement_changed.emit()
        except Exception as exc:
            self._notify(str(exc))

    def _confirm(self) -> None:
        try:
            payload = self._request_payload()
            answer = QMessageBox.question(
                self,
                "Confirm Settlement",
                "Confirm this FinancePeriod settlement? Confirmed settlements close the period for normal ledger mutation.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No,
            )
            if answer != QMessageBox.StandardButton.Yes:
                return
            self._settlement_service.confirm(**payload)
            self.settlement_changed.emit()
        except Exception as exc:
            self._notify(str(exc))

    def _reopen(self) -> None:
        reason, accepted = QInputDialog.getText(
            self,
            "Reopen Settlement",
            "Reason *:",
        )
        if not accepted:
            return
        try:
            self._settlement_service.reopen(
                target_date=self._target_date,
                reason=reason,
            )
            self.settlement_changed.emit()
        except Exception as exc:
            self._notify(str(exc))

    def _apply_write_state(self) -> None:
        is_draft = self._loaded_status == "DRAFT"
        save_capability = (
            Capability.FINANCE_SETTLEMENT_CREATE
            if self._loaded_id is None
            else Capability.FINANCE_SETTLEMENT_UPDATE
        )
        editable = can_mutate(
            write_enabled=self._write_enabled,
            capability=save_capability,
            domain_allowed=is_draft,
        )
        confirmable = editable and has_capability(
            Capability.FINANCE_SETTLEMENT_CONFIRM
        )
        reopenable = can_mutate(
            write_enabled=self._write_enabled,
            capability=Capability.FINANCE_SETTLEMENT_REOPEN,
            domain_allowed=self._loaded_status == "CONFIRMED",
        )
        for widget in (
            self.opening_cash,
            self.opening_bank,
            self.actual_cash,
            self.actual_bank,
            self.comment_edit,
        ):
            widget.setEnabled(editable)
        self.save_btn.setEnabled(editable)
        self.confirm_btn.setEnabled(confirmable)
        self.reopen_btn.setVisible(self._loaded_status == "CONFIRMED")
        self.reopen_btn.setEnabled(reopenable)

    def set_write_enabled(self, enabled: bool) -> None:
        self._write_enabled = bool(enabled)
        self._apply_write_state()
