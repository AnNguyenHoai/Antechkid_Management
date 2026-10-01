# -*- coding: utf-8 -*-
"""Runtime-generated AnTechKids desktop icon.

Keeping the icon generated from Qt primitives avoids deployment-path differences
between source runs and PyInstaller one-file builds while still replacing the
platform default CenterManager avatar.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QFont, QIcon, QPainter, QPixmap


def build_application_icon(size: int = 128) -> QIcon:
    """Return a compact blue/orange AnTechKids ``AK`` application mark."""
    size = max(32, int(size))
    pixmap = QPixmap(size, size)
    pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)

    radius = max(8, int(size * 0.22))
    painter.setBrush(QColor("#1565C0"))
    painter.setPen(Qt.PenStyle.NoPen)
    painter.drawRoundedRect(0, 0, size, size, radius, radius)

    accent_height = max(8, int(size * 0.24))
    painter.setBrush(QColor("#F57C00"))
    painter.drawRoundedRect(0, size - accent_height, size, accent_height, radius, radius)
    painter.drawRect(0, size - accent_height, size, accent_height // 2)

    font = QFont("Arial")
    font.setBold(True)
    font.setPixelSize(max(18, int(size * 0.44)))
    painter.setFont(font)
    painter.setPen(QColor("#FFFFFF"))
    painter.drawText(0, 0, size, size - accent_height // 3, Qt.AlignmentFlag.AlignCenter, "AK")
    painter.end()

    return QIcon(pixmap)


__all__ = ["build_application_icon"]
