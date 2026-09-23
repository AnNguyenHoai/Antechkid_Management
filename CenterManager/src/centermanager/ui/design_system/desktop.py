# -*- coding: utf-8 -*-
"""Desktop production polish helpers for CenterManager.

UI-PROD-09 keeps desktop-only presentation behavior outside business screens:
window placement, geometry persistence, shell-safe text elision, and global
native-widget polish. Visual values continue to come from Design System V2
semantic tokens.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEvent, QObject, QSettings, QSize, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QResizeEvent
from PySide6.QtWidgets import QLabel, QMainWindow, QSizePolicy, QWidget

from .tokens import COLORS, COMPONENT_METRICS, FONT_FAMILY, RADIUS, SPACING, TYPOGRAPHY

_SETTINGS_ORGANIZATION = "AnTechKids"
_SETTINGS_APPLICATION = "CenterManager"
_GEOMETRY_KEY = "ui/desktop/window_geometry"


class ElidedLabel(QLabel):
    """QLabel that visually elides long text while preserving its public text.

    ``text()`` deliberately returns the full semantic value so existing shell
    contracts, accessibility tools, and callers are not coupled to the amount
    of horizontal space currently available on screen.
    """

    def __init__(
        self,
        text: str = "",
        *,
        elide_mode: Qt.TextElideMode = Qt.TextElideMode.ElideRight,
        parent: Optional[QWidget] = None,
    ) -> None:
        self._full_text = ""
        self._elide_mode = elide_mode
        super().__init__("", parent)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        self.setText(text)

    def setText(self, text: str) -> None:  # noqa: N802 - Qt public API compatibility
        self._full_text = str(text)
        self.setToolTip(self._full_text)
        self.setAccessibleName(self._full_text)
        self._refresh_display_text()

    def text(self) -> str:  # noqa: N802 - Qt public API compatibility
        return self._full_text

    def displayed_text(self) -> str:
        """Return the currently rendered (possibly elided) text."""
        return QLabel.text(self)

    def minimumSizeHint(self) -> QSize:  # noqa: N802 - Qt public API compatibility
        hint = super().minimumSizeHint()
        return QSize(0, hint.height())

    def sizeHint(self) -> QSize:  # noqa: N802 - Qt public API compatibility
        hint = super().sizeHint()
        width = self.fontMetrics().horizontalAdvance(self._full_text)
        return QSize(width, hint.height())

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802
        super().resizeEvent(event)
        self._refresh_display_text()

    def _refresh_display_text(self) -> None:
        available_width = self.contentsRect().width()
        if available_width <= 0:
            rendered = self._full_text
        else:
            rendered = self.fontMetrics().elidedText(
                self._full_text,
                self._elide_mode,
                available_width,
            )
        QLabel.setText(self, rendered)


def desktop_stylesheet() -> str:
    """Return light-touch styling for native desktop chrome and overflow UI."""
    return f"""
        QToolTip {{
            background: {COLORS['gray_900']};
            color: {COLORS['text_inverse']};
            border: none;
            border-radius: {RADIUS['sm']}px;
            padding: {SPACING['xs']}px {SPACING['sm']}px;
            font-family: {FONT_FAMILY};
            font-size: {TYPOGRAPHY['caption']}px;
        }}
        QMenu {{
            background: {COLORS['surface_page']};
            color: {COLORS['text_primary']};
            border: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_default']};
            border-radius: {RADIUS['md']}px;
            padding: {SPACING['xs']}px;
            font-family: {FONT_FAMILY};
            font-size: {TYPOGRAPHY['body_small']}px;
        }}
        QMenu::item {{
            padding: {SPACING['sm']}px {SPACING['md']}px;
            border-radius: {RADIUS['sm']}px;
        }}
        QMenu::item:selected {{
            background: {COLORS['surface_hover']};
            color: {COLORS['text_primary']};
        }}
        QMenu::item:disabled {{
            color: {COLORS['text_disabled']};
        }}
        QMenu::separator {{
            height: {COMPONENT_METRICS['border_width']}px;
            background: {COLORS['border_subtle']};
            margin: {SPACING['xs']}px {SPACING['sm']}px;
        }}
        QScrollBar:vertical {{
            background: transparent;
            width: {SPACING['md']}px;
            margin: 0;
        }}
        QScrollBar::handle:vertical {{
            background: {COLORS['gray_400']};
            min-height: {SPACING['xxl']}px;
            border-radius: {RADIUS['sm']}px;
            margin: {SPACING['xs']}px;
        }}
        QScrollBar::handle:vertical:hover {{
            background: {COLORS['gray_500']};
        }}
        QScrollBar::add-line:vertical,
        QScrollBar::sub-line:vertical,
        QScrollBar::add-page:vertical,
        QScrollBar::sub-page:vertical {{
            background: transparent;
            height: 0;
        }}
        QScrollBar:horizontal {{
            background: transparent;
            height: {SPACING['md']}px;
            margin: 0;
        }}
        QScrollBar::handle:horizontal {{
            background: {COLORS['gray_400']};
            min-width: {SPACING['xxl']}px;
            border-radius: {RADIUS['sm']}px;
            margin: {SPACING['xs']}px;
        }}
        QScrollBar::handle:horizontal:hover {{
            background: {COLORS['gray_500']};
        }}
        QScrollBar::add-line:horizontal,
        QScrollBar::sub-line:horizontal,
        QScrollBar::add-page:horizontal,
        QScrollBar::sub-page:horizontal {{
            background: transparent;
            width: 0;
        }}
        QLineEdit:focus,
        QComboBox:focus,
        QDateEdit:focus,
        QPlainTextEdit:focus,
        QTextEdit:focus {{
            border-color: {COLORS['focus_ring']};
        }}
    """


def _settings() -> QSettings:
    return QSettings(_SETTINGS_ORGANIZATION, _SETTINGS_APPLICATION)


def _is_window_on_available_screen(window: QMainWindow) -> bool:
    frame = window.frameGeometry()
    screens = QGuiApplication.screens()
    return any(frame.intersects(screen.availableGeometry()) for screen in screens)


def apply_desktop_window_policy(
    window: QMainWindow,
    *,
    settings: Optional[QSettings] = None,
) -> bool:
    """Restore valid geometry or choose a centered, screen-aware first size.

    Returns ``True`` when persisted geometry was restored. The default size is
    intentionally derived from the available desktop rather than a second set
    of hard-coded layout constants; MainWindow's existing minimum size remains
    authoritative.
    """
    settings = settings or _settings()
    stored_geometry = settings.value(_GEOMETRY_KEY)
    if stored_geometry and window.restoreGeometry(stored_geometry):
        if _is_window_on_available_screen(window):
            return True

    screen = QGuiApplication.primaryScreen()
    if screen is None:
        return False

    available = screen.availableGeometry()
    minimum = window.minimumSize()
    target_width = max(minimum.width(), int(available.width() * 0.86))
    target_height = max(minimum.height(), int(available.height() * 0.86))
    target_width = min(target_width, available.width()) if available.width() >= minimum.width() else minimum.width()
    target_height = min(target_height, available.height()) if available.height() >= minimum.height() else minimum.height()

    window.resize(target_width, target_height)
    x = max(available.x(), available.x() + (available.width() - target_width) // 2)
    y = max(available.y(), available.y() + (available.height() - target_height) // 2)
    window.move(x, y)
    return False


class DesktopWindowPolisher(QObject):
    """Persist desktop geometry without coupling MainWindow close logic to UI."""

    def __init__(
        self,
        window: QMainWindow,
        *,
        settings: Optional[QSettings] = None,
    ) -> None:
        super().__init__(window)
        self._window = window
        self._settings = settings or _settings()
        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(250)
        self._save_timer.timeout.connect(self.save_geometry)
        window.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        if watched is self._window and event.type() in (
            QEvent.Type.Move,
            QEvent.Type.Resize,
            QEvent.Type.WindowStateChange,
        ):
            if self._window.isVisible() and not self._window.isMinimized():
                self._save_timer.start()
        return super().eventFilter(watched, event)

    def save_geometry(self) -> None:
        if self._window.isMinimized():
            return
        self._settings.setValue(_GEOMETRY_KEY, self._window.saveGeometry())


def install_desktop_polish(window: QWidget) -> Optional[DesktopWindowPolisher]:
    """Install UI-PROD-09 behavior once on an owning QMainWindow."""
    if not isinstance(window, QMainWindow):
        return None

    existing = getattr(window, "_desktop_polish_controller", None)
    if isinstance(existing, DesktopWindowPolisher):
        return existing

    existing_style = window.styleSheet().strip()
    polish_style = desktop_stylesheet().strip()
    window.setStyleSheet(
        f"{existing_style}\n{polish_style}" if existing_style else polish_style
    )
    apply_desktop_window_policy(window)
    controller = DesktopWindowPolisher(window)
    window._desktop_polish_controller = controller
    return controller


__all__ = [
    "DesktopWindowPolisher",
    "ElidedLabel",
    "apply_desktop_window_policy",
    "desktop_stylesheet",
    "install_desktop_polish",
]
