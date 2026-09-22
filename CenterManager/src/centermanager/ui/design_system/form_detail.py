# -*- coding: utf-8 -*-
"""Reusable form and detail composition patterns for Design System V2.

These widgets sit one level above the low-level component foundation. They
standardize field labeling, inline validation, detail rows, content sections,
and edit-state feedback without introducing workspace or domain logic.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from .tokens import (
    COLORS,
    COMPONENT_METRICS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    STATES,
    TYPOGRAPHY,
)


class FormField(QWidget):
    """Labeled form control with helper text and inline validation feedback."""

    def __init__(
        self,
        label: str,
        control: QWidget,
        *,
        required: bool = False,
        helper_text: str = "",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.control = control
        self._label_text = label
        self._required = required
        self._helper_text = helper_text
        self._error_message = ""

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(SPACING["xs"])

        self.label = QLabel(self._display_label())
        self.label.setObjectName("FormFieldLabel")
        self.label.setBuddy(control)
        root.addWidget(self.label)

        control.setSizePolicy(QSizePolicy.Policy.Expanding, control.sizePolicy().verticalPolicy())
        root.addWidget(control)

        self.message_label = QLabel(helper_text)
        self.message_label.setObjectName("FormFieldMessage")
        self.message_label.setWordWrap(True)
        self.message_label.setVisible(bool(helper_text))
        root.addWidget(self.message_label)

        self._apply_style()

    @property
    def has_error(self) -> bool:
        return bool(self._error_message)

    @property
    def error_message(self) -> str:
        return self._error_message

    def _display_label(self) -> str:
        return f"{self._label_text} *" if self._required else self._label_text

    def set_error(self, message: Optional[str]) -> None:
        self._error_message = (message or "").strip()
        if hasattr(self.control, "set_error"):
            self.control.set_error(self._error_message or None)
        else:
            self.control.setProperty(
                "validationState", "error" if self._error_message else "default"
            )
        self.message_label.setText(self._error_message or self._helper_text)
        self.message_label.setProperty(
            "messageState", "error" if self._error_message else "helper"
        )
        self.message_label.setVisible(bool(self._error_message or self._helper_text))
        self._apply_style()

    def clear_error(self) -> None:
        self.set_error(None)

    def _apply_style(self) -> None:
        message_color = (
            COLORS["state_danger"] if self.has_error else COLORS["text_muted"]
        )
        self.setStyleSheet(
            f"""
            QLabel#FormFieldLabel {{
                color: {COLORS["text_secondary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["medium"]};
                border: none;
            }}
            QLabel#FormFieldMessage {{
                color: {message_color};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["caption"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
                border: none;
            }}
            """
        )


class FormSection(QFrame):
    """Compact section for a related group of form fields."""

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("FormSection")
        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["md"])

        self.title_label = QLabel(title)
        self.title_label.setObjectName("FormSectionTitle")
        self.title_label.setWordWrap(True)
        root.addWidget(self.title_label)

        self.description_label = QLabel(description)
        self.description_label.setObjectName("FormSectionDescription")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))
        root.addWidget(self.description_label)

        self.fields = QWidget()
        self.fields_layout = QVBoxLayout(self.fields)
        self.fields_layout.setContentsMargins(0, 0, 0, 0)
        self.fields_layout.setSpacing(SPACING["md"])
        root.addWidget(self.fields)

        self.setStyleSheet(
            f"""
            QFrame#FormSection {{
                background-color: {COLORS["surface_card"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
            }}
            QLabel#FormSectionTitle {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["card_title"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
                border: none;
            }}
            QLabel#FormSectionDescription {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                border: none;
            }}
            """
        )

    def add_field(self, field: FormField) -> FormField:
        self.fields_layout.addWidget(field)
        return field


class DetailRow(QWidget):
    """Consistent label/value row for read-only operational details."""

    def __init__(
        self,
        label: str,
        value: str = "—",
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        root = QHBoxLayout(self)
        root.setContentsMargins(0, SPACING["xs"], 0, SPACING["xs"])
        root.setSpacing(SPACING["lg"])

        self.label = QLabel(label)
        self.label.setObjectName("DetailRowLabel")
        self.label.setMinimumWidth(128)
        self.value_label = QLabel(value or "—")
        self.value_label.setObjectName("DetailRowValue")
        self.value_label.setWordWrap(True)
        self.value_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        root.addWidget(self.label)
        root.addWidget(self.value_label, 1)
        self._apply_style()

    @property
    def value(self) -> str:
        return self.value_label.text()

    def set_value(self, value: object) -> None:
        text = "" if value is None else str(value).strip()
        self.value_label.setText(text or "—")

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"""
            QLabel#DetailRowLabel {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["medium"]};
                border: none;
            }}
            QLabel#DetailRowValue {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
                border: none;
            }}
            """
        )


class DetailSection(QFrame):
    """Reusable read-only/detail container with a quiet section hierarchy."""

    def __init__(
        self,
        title: str,
        description: str = "",
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DetailSection")
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["lg"]
        )
        self._root.setSpacing(SPACING["sm"])

        self.title_label = QLabel(title)
        self.title_label.setObjectName("DetailSectionTitle")
        self._root.addWidget(self.title_label)

        self.description_label = QLabel(description)
        self.description_label.setObjectName("DetailSectionDescription")
        self.description_label.setWordWrap(True)
        self.description_label.setVisible(bool(description))
        self._root.addWidget(self.description_label)

        self.setStyleSheet(
            f"""
            QFrame#DetailSection {{
                background-color: {COLORS["surface_card"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
            }}
            QLabel#DetailSectionTitle {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["card_title"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
                border: none;
            }}
            QLabel#DetailSectionDescription {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                border: none;
            }}
            """
        )

    def add_row(self, label: str, value: str = "—") -> DetailRow:
        row = DetailRow(label, value, parent=self)
        self._root.addWidget(row)
        return row

    def add_widget(self, widget: QWidget) -> QWidget:
        self._root.addWidget(widget)
        return widget


class EditStateBanner(QFrame):
    """Non-blocking feedback for read-only, editing, or externally locked state."""

    _STATE_COPY = {
        "readonly": ("Read-only mode", "Changes are disabled until edit mode is active."),
        "editing": ("Editing enabled", "Changes can be made and saved in this workspace."),
        "locked": ("Editing unavailable", "Another editor currently owns the write session."),
    }

    def __init__(
        self,
        state: str = "readonly",
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("EditStateBanner")
        root = QHBoxLayout(self)
        root.setContentsMargins(
            SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"]
        )
        root.setSpacing(SPACING["sm"])

        self.title_label = QLabel()
        self.title_label.setObjectName("EditStateTitle")
        self.message_label = QLabel()
        self.message_label.setObjectName("EditStateMessage")
        self.message_label.setWordWrap(True)
        root.addWidget(self.title_label)
        root.addWidget(self.message_label, 1)
        self._state = "readonly"
        self.set_state(state)

    @property
    def state(self) -> str:
        return self._state

    def set_state(self, state: str, message: Optional[str] = None) -> None:
        if state not in self._STATE_COPY:
            raise ValueError(f"Unsupported edit state: {state}")
        self._state = state
        title, default_message = self._STATE_COPY[state]
        self.title_label.setText(title)
        self.message_label.setText(message or default_message)
        self.setProperty("editState", state)
        self._apply_style()

    def _apply_style(self) -> None:
        palette = {
            "readonly": STATES["info"],
            "editing": STATES["success"],
            "locked": STATES["warning"],
        }[self._state]
        self.setStyleSheet(
            f"""
            QFrame#EditStateBanner {{
                background-color: {palette["background"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {palette["border"]};
                border-radius: {RADIUS["md"]}px;
            }}
            QLabel#EditStateTitle {{
                color: {palette["foreground"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
                border: none;
            }}
            QLabel#EditStateMessage {{
                color: {COLORS["text_secondary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                border: none;
            }}
            """
        )


__all__ = [
    "FormField",
    "FormSection",
    "DetailRow",
    "DetailSection",
    "EditStateBanner",
]
