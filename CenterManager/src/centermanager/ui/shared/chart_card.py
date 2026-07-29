# -*- coding: utf-8 -*-
from typing import Optional, List, Tuple
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING


class ChartCard(QFrame):
    """A card that displays a bar chart or pie chart."""
    def __init__(
        self,
        title: str,
        chart_type: str = "bar",  # "bar" or "pie"
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._title = title
        self._chart_type = chart_type
        self._data: List[Tuple[str, float]] = []
        self._colors = [
            COLORS['primary'], COLORS['primary_light'],
            COLORS['success'], COLORS['warning'], COLORS['danger'],
            "#ab47bc", "#26a69a", "#42a5f5"
        ]
        self.setFrameStyle(QFrame.Shape.Box | QFrame.Shadow.Plain)
        self.setStyleSheet(f"""
            QFrame {{
                border: 1px solid {COLORS['border_light']};
                border-radius: 8px;
                background: {COLORS['surface']};
                padding: {SPACING['sm']}px;
            }}
        """)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumHeight(200)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING['sm'], SPACING['sm'], SPACING['sm'], SPACING['sm'])
        layout.setSpacing(SPACING['xs'])

        title_label = QLabel(title)
        title_label.setStyleSheet(f"""
            font-size: {TYPOGRAPHY['card_title']}px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        """)
        layout.addWidget(title_label)

        self.chart_widget = ChartWidget(self._chart_type)
        self.chart_widget.setData(self._data, self._colors)
        layout.addWidget(self.chart_widget)

    def set_data(self, data: List[Tuple[str, float]]) -> None:
        self._data = data
        self.chart_widget.setData(data, self._colors)
        self.chart_widget.update()


class ChartWidget(QWidget):
    def __init__(self, chart_type: str = "bar", parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._chart_type = chart_type
        self._data: List[Tuple[str, float]] = []
        self._colors: List[str] = []
        self.setMinimumHeight(150)

    def setData(self, data: List[Tuple[str, float]], colors: List[str]) -> None:
        self._data = data
        self._colors = colors
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        margin = 20
        chart_rect = rect.adjusted(margin, margin, -margin, -margin)

        if not self._data:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No data")
            return

        if self._chart_type == "bar":
            self._draw_bar_chart(painter, chart_rect)
        elif self._chart_type == "pie":
            self._draw_pie_chart(painter, chart_rect)

    def _draw_bar_chart(self, painter: QPainter, rect: QRectF) -> None:
        total = sum(v for _, v in self._data)
        if total == 0:
            return
        n = len(self._data)
        bar_width = rect.width() / (n * 1.5)
        max_val = max(v for _, v in self._data) * 1.2

        for i, (label, value) in enumerate(self._data):
            x = rect.x() + i * (bar_width * 1.5) + bar_width * 0.25
            height = (value / max_val) * rect.height()
            y = rect.y() + rect.height() - height
            color = QColor(self._colors[i % len(self._colors)])
            painter.fillRect(QRectF(x, y, bar_width, height), color)
            # Draw label
            painter.setPen(QColor(COLORS['text_secondary']))
            painter.setFont(QFont("Arial", 8))
            painter.drawText(QRectF(x, rect.y() + rect.height() + 2, bar_width, 15),
                             Qt.AlignmentFlag.AlignHCenter, label[:10])

    def _draw_pie_chart(self, painter: QPainter, rect: QRectF) -> None:
        total = sum(v for _, v in self._data)
        if total == 0:
            return
        start_angle = 0
        for i, (label, value) in enumerate(self._data):
            angle = (value / total) * 360 * 16  # 1/16 degree
            color = QColor(self._colors[i % len(self._colors)])
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawPie(rect, int(start_angle), int(angle))
            start_angle += angle