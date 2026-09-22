# -*- coding: utf-8 -*-
"""Production component foundation for CenterManager Design System V2.

UI-PROD-02 defines the canonical low-level widgets used by later workspace
migrations.  Visual values come exclusively from ``tokens.py``.
"""
from __future__ import annotations

from enum import Enum
from typing import Callable, Iterable, Optional, Tuple, Union

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from .tokens import (
    BADGE_COLORS,
    COLORS,
    COMPONENT_METRICS,
    CONTROL_SIZES,
    ELEVATION,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    STATES,
    TYPOGRAPHY,
)


class ComponentSize(str, Enum):
    SMALL = "sm"
    MEDIUM = "md"
    LARGE = "lg"


class ButtonVariant(str, Enum):
    PRIMARY = "primary"
    ACCENT = "accent"
    SECONDARY = "secondary"
    DANGER = "danger"
    GHOST = "ghost"


class BadgeTone(str, Enum):
    NEUTRAL = "neutral"
    PRIMARY = "primary"
    ACCENT = "accent"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"
    INFO = "info"


def _value(value):
    return value.value if isinstance(value, Enum) else str(value)


def _control_spec(size: Union[ComponentSize, str]):
    key = _value(size)
    if key not in CONTROL_SIZES:
        raise ValueError(f"Unsupported component size: {key}")
    return CONTROL_SIZES[key]


def _tone_colors(tone: Union[BadgeTone, str]) -> Tuple[str, str, str]:
    key = _value(tone)
    palette = {
        "neutral": (
            COLORS["gray_100"],
            COLORS["text_secondary"],
            COLORS["border_default"],
        ),
        "primary": (
            COLORS["blue_50"],
            COLORS["action_primary_hover"],
            COLORS["action_primary"],
        ),
        "accent": (
            COLORS["state_warning_bg"],
            COLORS["action_accent_hover"],
            COLORS["action_accent"],
        ),
        "success": (
            STATES["success"]["background"],
            STATES["success"]["foreground"],
            STATES["success"]["border"],
        ),
        "warning": (
            STATES["warning"]["background"],
            STATES["warning"]["foreground"],
            STATES["warning"]["border"],
        ),
        "danger": (
            STATES["danger"]["background"],
            STATES["danger"]["foreground"],
            STATES["danger"]["border"],
        ),
        "info": (
            STATES["info"]["background"],
            STATES["info"]["foreground"],
            STATES["info"]["border"],
        ),
    }
    if key not in palette:
        raise ValueError(f"Unsupported badge tone: {key}")
    return palette[key]


def _button_colors(variant: Union[ButtonVariant, str]):
    key = _value(variant)
    palettes = {
        "primary": {
            "bg": COLORS["action_primary"],
            "fg": COLORS["text_inverse"],
            "border": COLORS["action_primary"],
            "hover_bg": COLORS["action_primary_hover"],
            "hover_border": COLORS["action_primary_hover"],
            "pressed_bg": COLORS["action_primary_hover"],
        },
        "accent": {
            "bg": COLORS["action_accent"],
            "fg": COLORS["text_inverse"],
            "border": COLORS["action_accent"],
            "hover_bg": COLORS["action_accent_hover"],
            "hover_border": COLORS["action_accent_hover"],
            "pressed_bg": COLORS["action_accent_hover"],
        },
        "secondary": {
            "bg": COLORS["surface_card"],
            "fg": COLORS["text_secondary"],
            "border": COLORS["border_strong"],
            "hover_bg": COLORS["surface_hover"],
            "hover_border": COLORS["action_primary"],
            "pressed_bg": COLORS["surface_pressed"],
        },
        "danger": {
            "bg": COLORS["surface_card"],
            "fg": COLORS["state_danger"],
            "border": COLORS["state_danger"],
            "hover_bg": COLORS["state_danger_hover_bg"],
            "hover_border": COLORS["state_danger"],
            "pressed_bg": COLORS["state_danger_pressed_bg"],
        },
        "ghost": {
            "bg": COLORS["surface_card"],
            "fg": COLORS["text_secondary"],
            "border": COLORS["surface_card"],
            "hover_bg": COLORS["surface_hover"],
            "hover_border": COLORS["surface_hover"],
            "pressed_bg": COLORS["surface_pressed"],
        },
    }
    if key not in palettes:
        raise ValueError(f"Unsupported button variant: {key}")
    return palettes[key]


class Button(QPushButton):
    """Canonical action button with semantic variants and sizes."""

    def __init__(
        self,
        text: str,
        *,
        variant: Union[ButtonVariant, str] = ButtonVariant.PRIMARY,
        size: Union[ComponentSize, str] = ComponentSize.MEDIUM,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(text, parent)
        self._variant = _value(variant)
        self._size = _value(size)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(text)
        self._apply_style()

    @property
    def variant(self) -> str:
        return self._variant

    def set_variant(self, variant: Union[ButtonVariant, str]) -> None:
        self._variant = _value(variant)
        self._apply_style()

    def set_size(self, size: Union[ComponentSize, str]) -> None:
        self._size = _value(size)
        self._apply_style()

    def _apply_style(self) -> None:
        spec = _control_spec(self._size)
        palette = _button_colors(self._variant)
        self.setFixedHeight(spec["height"])
        self.setStyleSheet(
            f"""
            QPushButton {{
                background-color: {palette["bg"]};
                color: {palette["fg"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {palette["border"]};
                border-radius: {RADIUS["md"]}px;
                padding: 0 {spec["padding_x"]}px;
                font-family: {FONT_FAMILY};
                font-size: {spec["font_size"]}px;
                font-weight: {FONT_WEIGHTS["medium"]};
            }}
            QPushButton:hover {{
                background-color: {palette["hover_bg"]};
                border-color: {palette["hover_border"]};
            }}
            QPushButton:pressed {{
                background-color: {palette["pressed_bg"]};
            }}
            QPushButton:focus {{
                border-color: {COLORS["focus_ring"]};
            }}
            QPushButton:disabled {{
                background-color: {STATES["disabled"]["background"]};
                color: {STATES["disabled"]["foreground"]};
                border-color: {STATES["disabled"]["border"]};
            }}
            """
        )


class Input(QLineEdit):
    """Canonical single-line text input with validation state support."""

    def __init__(
        self,
        placeholder: str = "",
        *,
        size: Union[ComponentSize, str] = ComponentSize.MEDIUM,
        clearable: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._size = _value(size)
        self._error_message = ""
        self.setPlaceholderText(placeholder)
        self.setClearButtonEnabled(clearable)
        self.setAccessibleName(placeholder or "Text input")
        self._apply_style()

    @property
    def error_message(self) -> str:
        return self._error_message

    @property
    def has_error(self) -> bool:
        return bool(self._error_message)

    def set_error(self, message: Optional[str]) -> None:
        self._error_message = (message or "").strip()
        self.setToolTip(self._error_message)
        self.setProperty("validationState", "error" if self._error_message else "default")
        self._apply_style()

    def clear_error(self) -> None:
        self.set_error(None)

    def _apply_style(self) -> None:
        spec = _control_spec(self._size)
        border = COLORS["state_danger"] if self.has_error else COLORS["border_strong"]
        self.setFixedHeight(spec["height"])
        self.setStyleSheet(
            f"""
            QLineEdit {{
                background-color: {COLORS["surface_card"]};
                color: {COLORS["text_primary"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {border};
                border-radius: {RADIUS["md"]}px;
                padding: 0 {spec["padding_x"]}px;
                font-family: {FONT_FAMILY};
                font-size: {spec["font_size"]}px;
                selection-background-color: {COLORS["action_primary_selected"]};
            }}
            QLineEdit:hover {{
                border-color: {COLORS["border_strong"]};
            }}
            QLineEdit:focus {{
                border-color: {COLORS["focus_ring"]};
            }}
            QLineEdit:disabled {{
                background-color: {STATES["disabled"]["background"]};
                color: {STATES["disabled"]["foreground"]};
                border-color: {STATES["disabled"]["border"]};
            }}
            """
        )


class Select(QComboBox):
    """Canonical select control supporting text or ``(label, data)`` options."""

    def __init__(
        self,
        options: Optional[Iterable[Union[str, Tuple[str, object]]]] = None,
        *,
        placeholder: Optional[str] = None,
        size: Union[ComponentSize, str] = ComponentSize.MEDIUM,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._size = _value(size)
        self._error_message = ""
        if placeholder:
            self.addItem(placeholder, None)
            self.setCurrentIndex(0)
        if options:
            self.set_options(options, preserve_placeholder=bool(placeholder))
        self.setAccessibleName(placeholder or "Select")
        self._apply_style()

    @property
    def has_error(self) -> bool:
        return bool(self._error_message)

    def set_options(
        self,
        options: Iterable[Union[str, Tuple[str, object]]],
        *,
        preserve_placeholder: bool = False,
    ) -> None:
        placeholder = None
        if preserve_placeholder and self.count():
            placeholder = (self.itemText(0), self.itemData(0))
        self.clear()
        if placeholder is not None:
            self.addItem(placeholder[0], placeholder[1])
        for option in options:
            if isinstance(option, tuple):
                self.addItem(str(option[0]), option[1])
            else:
                self.addItem(str(option))

    def set_error(self, message: Optional[str]) -> None:
        self._error_message = (message or "").strip()
        self.setToolTip(self._error_message)
        self.setProperty("validationState", "error" if self._error_message else "default")
        self._apply_style()

    def clear_error(self) -> None:
        self.set_error(None)

    def _apply_style(self) -> None:
        spec = _control_spec(self._size)
        border = COLORS["state_danger"] if self.has_error else COLORS["border_strong"]
        self.setFixedHeight(spec["height"])
        self.setStyleSheet(
            f"""
            QComboBox {{
                background-color: {COLORS["surface_card"]};
                color: {COLORS["text_primary"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {border};
                border-radius: {RADIUS["md"]}px;
                padding: 0 {spec["padding_x"]}px;
                font-family: {FONT_FAMILY};
                font-size: {spec["font_size"]}px;
            }}
            QComboBox:hover {{
                border-color: {COLORS["border_strong"]};
            }}
            QComboBox:focus {{
                border-color: {COLORS["focus_ring"]};
            }}
            QComboBox:disabled {{
                background-color: {STATES["disabled"]["background"]};
                color: {STATES["disabled"]["foreground"]};
                border-color: {STATES["disabled"]["border"]};
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS["surface_page"]};
                color: {COLORS["text_primary"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
                selection-background-color: {COLORS["action_primary_selected"]};
                selection-color: {COLORS["action_primary_hover"]};
            }}
            """
        )


class Badge(QLabel):
    """Compact semantic badge. ``status`` may resolve through BADGE_COLORS."""

    def __init__(
        self,
        text: str,
        *,
        tone: Union[BadgeTone, str] = BadgeTone.NEUTRAL,
        status: Optional[str] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._tone = _value(tone)
        self._status = status.upper() if status else None
        self.setText(text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        self._apply_style()

    @classmethod
    def from_status(cls, status: str, parent: Optional[QWidget] = None) -> "Badge":
        label = status.replace("_", " ").title()
        return cls(label, status=status, parent=parent)

    def set_tone(self, tone: Union[BadgeTone, str]) -> None:
        self._tone = _value(tone)
        self._status = None
        self._apply_style()

    def set_status(self, status: str) -> None:
        self._status = status.upper()
        self.setText(status.replace("_", " ").title())
        self._apply_style()

    def _apply_style(self) -> None:
        if self._status and self._status in BADGE_COLORS:
            colors = BADGE_COLORS[self._status]
            bg, fg, border = colors["bg"], colors["text"], colors["bg"]
        else:
            bg, fg, border = _tone_colors(self._tone)
        self.setFixedHeight(COMPONENT_METRICS["badge_height"])
        self.setStyleSheet(
            f"""
            QLabel {{
                background-color: {bg};
                color: {fg};
                border: {COMPONENT_METRICS["border_width"]}px solid {border};
                border-radius: {RADIUS["pill"]}px;
                padding: 0 {SPACING["sm"]}px;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["badge"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
            }}
            """
        )


class Card(QFrame):
    """Canonical content container with optional title/subtitle header."""

    def __init__(
        self,
        title: Optional[str] = None,
        subtitle: Optional[str] = None,
        *,
        elevation: str = "none",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignSystemCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self._root = QVBoxLayout(self)
        self._root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        self._root.setSpacing(SPACING["md"])

        if title:
            title_label = QLabel(title)
            title_label.setObjectName("DesignSystemCardTitle")
            title_label.setWordWrap(True)
            self._root.addWidget(title_label)
        if subtitle:
            subtitle_label = QLabel(subtitle)
            subtitle_label.setObjectName("DesignSystemCardSubtitle")
            subtitle_label.setWordWrap(True)
            self._root.addWidget(subtitle_label)

        self.content = QWidget()
        self.content.setObjectName("DesignSystemCardContent")
        self.content_layout = QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(SPACING["md"])
        self._root.addWidget(self.content)
        self._apply_style()
        self.set_elevation(elevation)

    def add_widget(self, widget: QWidget) -> None:
        self.content_layout.addWidget(widget)

    def set_elevation(self, elevation: str) -> None:
        if elevation not in ELEVATION:
            raise ValueError(f"Unsupported elevation: {elevation}")
        spec = ELEVATION[elevation]
        if spec["alpha"] <= 0:
            self.setGraphicsEffect(None)
            return
        effect = QGraphicsDropShadowEffect(self)
        color = QColor(COLORS["shadow_color"])
        color.setAlpha(spec["alpha"])
        effect.setColor(color)
        effect.setBlurRadius(spec["blur_radius"])
        effect.setOffset(spec["x_offset"], spec["y_offset"])
        self.setGraphicsEffect(effect)

    def _apply_style(self) -> None:
        self.setStyleSheet(
            f"""
            QFrame#DesignSystemCard {{
                background-color: {COLORS["surface_card"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
            }}
            QLabel#DesignSystemCardTitle {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["card_title"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
                border: none;
            }}
            QLabel#DesignSystemCardSubtitle {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
                border: none;
            }}
            QWidget#DesignSystemCardContent {{
                background-color: transparent;
                border: none;
            }}
            """
        )


class Toolbar(QFrame):
    """Horizontal application toolbar with explicit start/end zones."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("DesignSystemToolbar")
        self.setMinimumHeight(COMPONENT_METRICS["toolbar_height"])
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(
            SPACING["md"], SPACING["sm"], SPACING["md"], SPACING["sm"]
        )
        self._layout.setSpacing(SPACING["sm"])

        self.start_zone = QHBoxLayout()
        self.start_zone.setSpacing(SPACING["sm"])
        self.end_zone = QHBoxLayout()
        self.end_zone.setSpacing(SPACING["sm"])
        self._layout.addLayout(self.start_zone)
        self._layout.addStretch()
        self._layout.addLayout(self.end_zone)

        self.setStyleSheet(
            f"""
            QFrame#DesignSystemToolbar {{
                background-color: {COLORS["surface_page"]};
                border: none;
                border-bottom: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
            }}
            """
        )

    def add_widget(self, widget: QWidget, *, align: str = "start") -> QWidget:
        if align == "start":
            self.start_zone.addWidget(widget)
        elif align == "end":
            self.end_zone.addWidget(widget)
        else:
            raise ValueError("align must be 'start' or 'end'")
        return widget

    def add_action(
        self,
        text: str,
        callback: Optional[Callable[[], None]] = None,
        *,
        variant: Union[ButtonVariant, str] = ButtonVariant.SECONDARY,
        align: str = "end",
    ) -> Button:
        button = Button(text, variant=variant, size=ComponentSize.SMALL)
        if callback is not None:
            button.clicked.connect(callback)
        self.add_widget(button, align=align)
        return button


class Tabs(QTabWidget):
    """Canonical tab container for page-local navigation."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setDocumentMode(True)
        self.setMovable(False)
        self.setTabsClosable(False)
        self.setStyleSheet(
            f"""
            QTabWidget::pane {{
                background-color: {COLORS["surface_page"]};
                border: none;
                border-top: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
            }}
            QTabBar::tab {{
                background-color: {COLORS["surface_page"]};
                color: {COLORS["text_secondary"]};
                min-width: {COMPONENT_METRICS["tab_min_width"]}px;
                min-height: {COMPONENT_METRICS["tab_height"]}px;
                padding: 0 {SPACING["md"]}px;
                border: none;
                border-bottom: {COMPONENT_METRICS["tab_indicator_width"]}px solid transparent;
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["medium"]};
            }}
            QTabBar::tab:hover {{
                background-color: {COLORS["surface_hover"]};
                color: {COLORS["text_primary"]};
            }}
            QTabBar::tab:selected {{
                color: {COLORS["action_primary"]};
                border-bottom-color: {COLORS["action_primary"]};
            }}
            QTabBar::tab:disabled {{
                color: {COLORS["text_disabled"]};
            }}
            """
        )

    def add_page(self, widget: QWidget, label: str, *, enabled: bool = True) -> int:
        index = self.addTab(widget, label)
        self.setTabEnabled(index, enabled)
        return index


class Dialog(QDialog):
    """Standard dialog shell with title, body and action footer."""

    def __init__(
        self,
        title: str,
        *,
        description: Optional[str] = None,
        primary_text: str = "Save",
        cancel_text: str = "Cancel",
        show_cancel: bool = True,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignSystemDialog")
        self.setWindowTitle(title)
        self.setModal(True)
        self.setMinimumWidth(COMPONENT_METRICS["dialog_min_width"])
        self.setAccessibleName(title)

        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["xl"], SPACING["xl"], SPACING["xl"], SPACING["lg"]
        )
        root.setSpacing(SPACING["lg"])

        self.title_label = QLabel(title)
        self.title_label.setObjectName("DesignSystemDialogTitle")
        self.title_label.setWordWrap(True)
        root.addWidget(self.title_label)

        if description:
            description_label = QLabel(description)
            description_label.setObjectName("DesignSystemDialogDescription")
            description_label.setWordWrap(True)
            root.addWidget(description_label)

        self.body = QWidget()
        self.body_layout = QVBoxLayout(self.body)
        self.body_layout.setContentsMargins(0, 0, 0, 0)
        self.body_layout.setSpacing(SPACING["md"])
        root.addWidget(self.body)

        footer = QHBoxLayout()
        footer.setSpacing(SPACING["sm"])
        footer.addStretch()

        self.cancel_button = Button(
            cancel_text,
            variant=ButtonVariant.SECONDARY,
            parent=self,
        )
        self.cancel_button.clicked.connect(self.reject)
        self.cancel_button.setVisible(show_cancel)
        footer.addWidget(self.cancel_button)

        self.primary_button = Button(
            primary_text,
            variant=ButtonVariant.PRIMARY,
            parent=self,
        )
        self.primary_button.clicked.connect(self.accept)
        footer.addWidget(self.primary_button)
        root.addLayout(footer)

        self.setStyleSheet(
            f"""
            QDialog#DesignSystemDialog {{
                background-color: {COLORS["surface_page"]};
            }}
            QLabel#DesignSystemDialogTitle {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["section_title"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
            }}
            QLabel#DesignSystemDialogDescription {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
            }}
            """
        )

    def add_body_widget(self, widget: QWidget) -> QWidget:
        self.body_layout.addWidget(widget)
        return widget

    def set_primary_enabled(self, enabled: bool) -> None:
        self.primary_button.setEnabled(enabled)


class Skeleton(QFrame):
    """Token-driven loading placeholder."""

    def __init__(
        self,
        height: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignSystemSkeleton")
        self.setFixedHeight(height or COMPONENT_METRICS["skeleton_row_height"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setStyleSheet(
            f"""
            QFrame#DesignSystemSkeleton {{
                background-color: {COLORS["gray_100"]};
                border: none;
                border-radius: {RADIUS["md"]}px;
            }}
            """
        )


class StateView(QWidget):
    """Base presentation for empty/error/loading content states."""

    def __init__(
        self,
        title: str,
        message: str = "",
        *,
        tone: Union[BadgeTone, str] = BadgeTone.NEUTRAL,
        symbol: Optional[str] = None,
        action_text: Optional[str] = None,
        action_callback: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._root = QVBoxLayout(self)
        self._root.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._root.setContentsMargins(
            SPACING["xl"], SPACING["xl"], SPACING["xl"], SPACING["xl"]
        )
        self._root.setSpacing(SPACING["sm"])

        if symbol:
            bg, fg, _ = _tone_colors(tone)
            symbol_label = QLabel(symbol)
            symbol_label.setObjectName("DesignSystemStateSymbol")
            symbol_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            symbol_label.setFixedSize(
                COMPONENT_METRICS["state_symbol_size"],
                COMPONENT_METRICS["state_symbol_size"],
            )
            symbol_label.setStyleSheet(
                f"""
                QLabel#DesignSystemStateSymbol {{
                    background-color: {bg};
                    color: {fg};
                    border-radius: {RADIUS["circle"]}px;
                    font-family: {FONT_FAMILY};
                    font-size: {TYPOGRAPHY["icon"]}px;
                    font-weight: {FONT_WEIGHTS["bold"]};
                }}
                """
            )
            self._root.addWidget(symbol_label, alignment=Qt.AlignmentFlag.AlignCenter)

        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.title_label.setWordWrap(True)
        self.title_label.setMaximumWidth(COMPONENT_METRICS["state_max_width"])
        self.title_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["section_title"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
            }}
            """
        )
        self._root.addWidget(self.title_label)

        self.message_label = QLabel(message)
        self.message_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.message_label.setWordWrap(True)
        self.message_label.setMaximumWidth(COMPONENT_METRICS["state_max_width"])
        self.message_label.setVisible(bool(message))
        self.message_label.setStyleSheet(
            f"""
            QLabel {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
            }}
            """
        )
        self._root.addWidget(self.message_label)

        self.action_button: Optional[Button] = None
        if action_text:
            self.action_button = Button(
                action_text,
                variant=ButtonVariant.SECONDARY,
                size=ComponentSize.SMALL,
                parent=self,
            )
            if action_callback is not None:
                self.action_button.clicked.connect(action_callback)
            self._root.addWidget(
                self.action_button,
                alignment=Qt.AlignmentFlag.AlignCenter,
            )


class EmptyState(StateView):
    """Standard no-content state."""

    def __init__(
        self,
        icon: Optional[str] = None,
        title: str = "No data",
        description: str = "",
        action_text: Optional[str] = None,
        action_callback: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            title,
            description,
            tone=BadgeTone.NEUTRAL,
            symbol=icon,
            action_text=action_text,
            action_callback=action_callback,
            parent=parent,
        )


class LoadingState(QWidget):
    """Standard loading state with optional skeleton rows."""

    def __init__(
        self,
        message: str = "Loading...",
        *,
        skeleton_rows: int = 0,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        layout.setSpacing(SPACING["sm"])

        if skeleton_rows > 0:
            for _ in range(skeleton_rows):
                layout.addWidget(Skeleton(parent=self))
            layout.addStretch()
        else:
            layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
            progress = QProgressBar(self)
            progress.setRange(0, 0)
            progress.setTextVisible(False)
            progress.setFixedSize(
                COMPONENT_METRICS["loading_width"],
                COMPONENT_METRICS["loading_height"],
            )
            progress.setStyleSheet(
                f"""
                QProgressBar {{
                    background-color: {COLORS["gray_100"]};
                    border: none;
                    border-radius: {RADIUS["sm"]}px;
                }}
                QProgressBar::chunk {{
                    background-color: {COLORS["action_primary"]};
                    border-radius: {RADIUS["sm"]}px;
                }}
                """
            )
            layout.addWidget(progress, alignment=Qt.AlignmentFlag.AlignCenter)
            label = QLabel(message)
            label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            label.setStyleSheet(
                f"""
                QLabel {{
                    color: {COLORS["text_muted"]};
                    font-family: {FONT_FAMILY};
                    font-size: {TYPOGRAPHY["body"]}px;
                }}
                """
            )
            layout.addWidget(label)


class ErrorState(StateView):
    """Standard recoverable error state."""

    def __init__(
        self,
        title: str = "Something went wrong",
        description: str = "",
        *,
        retry_text: Optional[str] = "Try again",
        retry_callback: Optional[Callable[[], None]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            title,
            description,
            tone=BadgeTone.DANGER,
            symbol="!",
            action_text=retry_text,
            action_callback=retry_callback,
            parent=parent,
        )
        if self.action_button is not None:
            self.action_button.set_variant(ButtonVariant.PRIMARY)


__all__ = [
    "ComponentSize",
    "ButtonVariant",
    "BadgeTone",
    "Button",
    "Input",
    "Select",
    "Badge",
    "Card",
    "Toolbar",
    "Tabs",
    "Dialog",
    "Skeleton",
    "StateView",
    "EmptyState",
    "LoadingState",
    "ErrorState",
]
