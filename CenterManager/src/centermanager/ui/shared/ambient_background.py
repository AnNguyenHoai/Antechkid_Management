# -*- coding: utf-8 -*-
"""Lightweight ambient shell background inspired by AnTechKids robotics/AI visuals."""
from __future__ import annotations

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QLinearGradient, QPainter, QPen
from PySide6.QtWidgets import QWidget

from centermanager.ui.design_system.tokens import COLORS


class AmbientBackground(QWidget):
    """Responsive, low-contrast technology/learning ambience for landing surfaces."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("AmbientBackground")
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent, True)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()

        base = QLinearGradient(0, 0, rect.width(), rect.height())
        base.setColorAt(0.0, QColor(COLORS["ambient_base_start"]))
        base.setColorAt(0.45, QColor(COLORS["ambient_base_mid"]))
        base.setColorAt(1.0, QColor(COLORS["ambient_base_end"]))
        painter.fillRect(rect, base)

        self._paint_warm_glow(painter, rect)
        self._paint_cool_glow(painter, rect)
        self._paint_network(painter, rect)
        self._paint_blocks(painter, rect)
        self._paint_chip(painter, rect)
        self._paint_gears(painter, rect)
        painter.end()

    @staticmethod
    def _with_alpha(color: str, alpha: int) -> QColor:
        value = QColor(color)
        value.setAlpha(alpha)
        return value

    @staticmethod
    def _paint_warm_glow(painter: QPainter, rect) -> None:
        gradient = QLinearGradient(0, rect.height(), rect.width() * 0.45, rect.height() * 0.55)
        gradient.setColorAt(0.0, QColor(245, 124, 0, 45))
        gradient.setColorAt(0.35, QColor(245, 124, 0, 14))
        gradient.setColorAt(1.0, QColor(245, 124, 0, 0))
        painter.fillRect(rect, gradient)

    @staticmethod
    def _paint_cool_glow(painter: QPainter, rect) -> None:
        gradient = QLinearGradient(rect.width(), 0, rect.width() * 0.48, rect.height() * 0.72)
        gradient.setColorAt(0.0, AmbientBackground._with_alpha(COLORS["action_primary"], 30))
        gradient.setColorAt(0.4, QColor(66, 165, 245, 12))
        gradient.setColorAt(1.0, QColor(66, 165, 245, 0))
        painter.fillRect(rect, gradient)

    @staticmethod
    def _paint_network(painter: QPainter, rect) -> None:
        pen = QPen(AmbientBackground._with_alpha(COLORS["ambient_network"], 24), 1)
        painter.setPen(pen)
        left = [
            (0.02, 0.18), (0.10, 0.08), (0.16, 0.28), (0.23, 0.14),
            (0.27, 0.34), (0.18, 0.52), (0.08, 0.43), (0.03, 0.62),
        ]
        right = [
            (0.76, 0.08), (0.86, 0.15), (0.96, 0.05), (0.92, 0.28),
            (0.82, 0.33), (0.98, 0.43), (0.88, 0.52), (0.74, 0.42),
        ]
        for points in (left, right):
            mapped = [QPointF(rect.width() * x, rect.height() * y) for x, y in points]
            for a, b in zip(mapped, mapped[1:]):
                painter.drawLine(a, b)
            painter.setBrush(AmbientBackground._with_alpha(COLORS["ambient_network"], 34))
            painter.setPen(Qt.PenStyle.NoPen)
            for point in mapped:
                painter.drawEllipse(point, 3, 3)
            painter.setPen(pen)

    @staticmethod
    def _paint_blocks(painter: QPainter, rect) -> None:
        x = rect.width() * 0.035
        y = rect.height() * 0.70
        size = max(44.0, min(rect.width(), rect.height()) * 0.08)
        pen = QPen(AmbientBackground._with_alpha(COLORS["ambient_network"], 22), 2)
        painter.setPen(pen)
        painter.setBrush(QColor(255, 255, 255, 60))
        for dx, dy, scale in ((0, 0, 1.0), (0.78, 0.20, 0.86), (0.35, -0.62, 0.72)):
            box = QRectF(x + dx * size, y + dy * size, size * scale, size * scale)
            painter.drawRoundedRect(box, 8, 8)
        painter.setPen(QPen(AmbientBackground._with_alpha(COLORS["action_primary"], 32), 2))
        painter.drawText(QRectF(x, y, size, size), Qt.AlignmentFlag.AlignCenter, "A")

    @staticmethod
    def _paint_chip(painter: QPainter, rect) -> None:
        size = max(54.0, min(rect.width(), rect.height()) * 0.09)
        x = rect.width() - size * 1.55
        y = rect.height() * 0.06
        chip = QRectF(x, y, size, size)
        painter.setPen(QPen(AmbientBackground._with_alpha(COLORS["action_primary"], 24), 2))
        painter.setBrush(AmbientBackground._with_alpha(COLORS["action_primary"], 10))
        painter.drawRoundedRect(chip, 10, 10)
        painter.setPen(QPen(QColor(25, 118, 210, 30), 2))
        painter.drawText(chip, Qt.AlignmentFlag.AlignCenter, "AI")
        for i in range(5):
            off = (i + 1) * size / 6
            painter.drawLine(QPointF(x - 12, y + off), QPointF(x, y + off))
            painter.drawLine(QPointF(x + size, y + off), QPointF(x + size + 12, y + off))
            painter.drawLine(QPointF(x + off, y - 12), QPointF(x + off, y))
            painter.drawLine(QPointF(x + off, y + size), QPointF(x + off, y + size + 12))

    @staticmethod
    def _paint_gears(painter: QPainter, rect) -> None:
        painter.setPen(QPen(AmbientBackground._with_alpha(COLORS["ambient_gear"], 20), 2))
        painter.setBrush(AmbientBackground._with_alpha(COLORS["ambient_gear"], 8))
        for x, y, radius in ((0.19, 0.24, 22), (0.225, 0.29, 14), (0.70, 0.22, 12)):
            center = QPointF(rect.width() * x, rect.height() * y)
            painter.drawEllipse(center, radius, radius)
            painter.drawEllipse(center, radius * 0.38, radius * 0.38)


__all__ = ["AmbientBackground"]
