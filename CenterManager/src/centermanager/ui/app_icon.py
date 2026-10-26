# -*- coding: utf-8 -*-
"""Deterministic vector icons for CenterManager UI.

Icons are rendered from inline SVG paths so Windows builds do not depend on
emoji/font fallback. No external font or asset file is required.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QColor, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import QLabel, QWidget

from centermanager.ui.design_system.tokens import COLORS, RADIUS


_PATHS = {
    "home": "M12 3 2 12h3v9h6v-6h2v6h6v-9h3L12 3zm0 2.7 7 6.3v7h-4v-6H9v6H7v-7l5-6.3z",
    "student": "M16 11c1.66 0 3-1.34 3-3s-1.34-3-3-3-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 3-1.34 3-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5C15 14.17 10.33 13 8 13zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z",
    "teacher": "M12 2 3 6v6c0 5 3.8 9.7 9 10 5.2-.3 9-5 9-10V6l-9-4zm-1 14-4-4 1.4-1.4 2.6 2.6 5.6-5.6L18 9l-7 7z",
    "class": "M3 4h18v4H3V4zm0 6h18v4H3v-4zm0 6h18v4H3v-4z",
    "finance": "M4 5h16a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2zm0 2v10h16V7H4zm11 3h5v4h-5v-4z",
    "employee": "M12 12c2.21 0 4-1.79 4-4s-1.79-4-4-4-4 1.79-4 4 1.79 4 4 4zm0 2c-3.31 0-8 1.66-8 5v1h16v-1c0-3.34-4.69-5-8-5z",
    "settings": "M19.14 12.94c.04-.31.06-.63.06-.94s-.02-.63-.07-.94l2.03-1.58-1.92-3.32-2.39.96a7.3 7.3 0 0 0-1.63-.95L14.86 3h-3.72l-.36 3.17c-.58.24-1.12.55-1.63.95l-2.39-.96-1.92 3.32 2.03 1.58c-.05.31-.07.64-.07.94 0 .31.02.63.07.94l-2.03 1.58 1.92 3.32 2.39-.96c.5.4 1.05.72 1.63.95l.36 3.17h3.72l.36-3.17c.58-.24 1.12-.55 1.63-.95l2.39.96 1.92-3.32-2.02-1.58zM13 15.5A3.5 3.5 0 1 1 13 8a3.5 3.5 0 0 1 0 7.5z",
    "reports": "M4 20h16v2H2V2h2v18zm3-2H5v-7h2v7zm5 0H9V6h3v12zm5 0h-3V9h3v9zm4 0h-2V4h2v14z",
    "open": "M8 5v2h7.59L5 17.59 6.41 19 17 8.41V16h2V5H8z",
}


class AppIcon(QLabel):
    """Small deterministic vector icon with optional rounded tile background."""

    def __init__(
        self,
        name: str,
        *,
        size: int = 18,
        color: str = COLORS["text_secondary"],
        tile_color: Optional[str] = None,
        tile_size: Optional[int] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._name = name if name in _PATHS else "reports"
        self._icon_size = int(size)
        self._color = color
        self._tile_color = tile_color
        self._tile_size = int(tile_size or size)
        self.setFixedSize(self._tile_size, self._tile_size)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self._render()

    def _render(self) -> None:
        scale = self.devicePixelRatioF()
        side = max(1, int(self._tile_size * scale))
        pixmap = QPixmap(side, side)
        pixmap.setDevicePixelRatio(scale)
        pixmap.fill(Qt.GlobalColor.transparent)

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        if self._tile_color:
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(QColor(self._tile_color))
            painter.drawRoundedRect(
                QRectF(0, 0, self._tile_size, self._tile_size),
                RADIUS["md"],
                RADIUS["md"],
            )

        svg = (
            '<svg xmlns="http://www.w3.org/2000/svg" width="24" height="24" '
            'viewBox="0 0 24 24">'
            f'<path fill="{self._color}" d="{_PATHS[self._name]}"/>'
            "</svg>"
        )
        renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
        inset = (self._tile_size - self._icon_size) / 2
        renderer.render(
            painter,
            QRectF(inset, inset, self._icon_size, self._icon_size),
        )
        painter.end()
        self.setPixmap(pixmap)

    def set_color(self, color: str) -> None:
        if color == self._color:
            return
        self._color = color
        self._render()


__all__ = ["AppIcon"]
