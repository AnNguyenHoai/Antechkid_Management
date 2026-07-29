# -*- coding: utf-8 -*-
from typing import Optional, List, Tuple
from PySide6.QtCore import Qt, QRectF
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QFrame, QSizePolicy
from PySide6.QtGui import QPainter, QColor, QPen, QBrush, QFont, QFontMetrics

from centermanager.ui.design_system.tokens import COLORS, TYPOGRAPHY, SPACING


class ChartCard(QFrame):
    """A card that displays a bar chart or pie chart with improved styling."""
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
            "#1976d2", "#42a5f5", "#66bb6a", "#ffa726", "#ef5350",
            "#ab47bc", "#26a69a", "#78909c"
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
        self.setMinimumHeight(220)

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
        self.setMinimumHeight(180)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)

    def setData(self, data: List[Tuple[str, float]], colors: List[str]) -> None:
        self._data = data
        self._colors = colors
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect()
        margin = 30
        chart_rect = rect.adjusted(margin, margin, -margin, -margin)

        if not self._data:
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "No data")
            return

        if self._chart_type == "bar":
            self._draw_bar_chart(painter, chart_rect)
        elif self._chart_type == "pie":
            self._draw_pie_chart(painter, chart_rect)

    def _draw_bar_chart(self, painter: QPainter, rect: QRectF) -> None:
        if not self._data:
            return

        # Sort data by value descending for better visual
        sorted_data = sorted(self._data, key=lambda x: x[1], reverse=True)
        n = len(sorted_data)
        if n == 0:
            return

        max_val = max(v for _, v in sorted_data) * 1.2
        if max_val == 0:
            max_val = 1

        # Bar width with spacing
        bar_spacing = rect.width() / (n * 1.8)
        bar_width = bar_spacing * 0.7
        if bar_width < 10:
            bar_width = 10

        # Draw axes
        painter.setPen(QPen(QColor(COLORS['text_muted']), 1))
        painter.drawLine(rect.x(), rect.y() + rect.height(), rect.x() + rect.width(), rect.y() + rect.height())
        painter.drawLine(rect.x(), rect.y(), rect.x(), rect.y() + rect.height())

        # Draw bars
        for i, (label, value) in enumerate(sorted_data):
            x = rect.x() + i * bar_spacing + (bar_spacing - bar_width) / 2
            height = (value / max_val) * rect.height()
            y = rect.y() + rect.height() - height
            color = QColor(self._colors[i % len(self._colors)])
            painter.fillRect(QRectF(x, y, bar_width, height), color)

            # Draw value on top of bar
            painter.setPen(QPen(QColor(COLORS['text_primary']), 1))
            painter.setFont(QFont("Arial", 9, QFont.Weight.Bold))
            value_text = f"{value:.1f}" if value % 1 != 0 else str(int(value))
            fm = QFontMetrics(painter.font())
            text_width = fm.horizontalAdvance(value_text)
            painter.drawText(QRectF(x + (bar_width - text_width) / 2, y - 18, text_width, 16),
                             Qt.AlignmentFlag.AlignCenter, value_text)

            # Draw label below x-axis
            painter.setPen(QPen(QColor(COLORS['text_muted']), 1))
            painter.setFont(QFont("Arial", 8))
            fm = QFontMetrics(painter.font())
            label_text = label if len(label) <= 10 else label[:10] + "…"
            label_width = fm.horizontalAdvance(label_text)
            painter.drawText(QRectF(x + (bar_width - label_width) / 2, rect.y() + rect.height() + 4, label_width, 16),
                             Qt.AlignmentFlag.AlignCenter, label_text)

        # Draw y-axis labels
        painter.setPen(QPen(QColor(COLORS['text_muted']), 1))
        painter.setFont(QFont("Arial", 8))
        for y_val in range(0, int(max_val) + 1, max(1, int(max_val // 4))):
            y_pos = rect.y() + rect.height() - (y_val / max_val) * rect.height()
            painter.drawText(QRectF(rect.x() - 30, y_pos - 8, 25, 16),
                             Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter, str(y_val))
            painter.drawLine(rect.x() - 4, y_pos, rect.x(), y_pos)

    def _draw_pie_chart(self, painter: QPainter, rect: QRectF) -> None:
        total = sum(v for _, v in self._data)
        if total == 0:
            return

        start_angle = 0
        legend_rect = QRectF(rect.x() + rect.width() * 0.65, rect.y(),
                             rect.width() * 0.3, rect.height())

        # Draw pie
        pie_rect = QRectF(rect.x(), rect.y(),
                          min(rect.width() * 0.6, rect.height()),
                          min(rect.width() * 0.6, rect.height()))
        pie_rect.moveCenter(rect.center() - QPointF(rect.width() * 0.1, 0))

        for i, (label, value) in enumerate(self._data):
            angle = (value / total) * 360 * 16  # 1/16 degree
            color = QColor(self._colors[i % len(self._colors)])
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawPie(pie_rect, int(start_angle), int(angle))
            start_angle += angle

        # Draw legend
        legend_y = legend_rect.y()
        for i, (label, value) in enumerate(self._data):
            color = QColor(self._colors[i % len(self._colors)])
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(Qt.PenStyle.NoPen))
            painter.drawRect(QRectF(legend_rect.x(), legend_y, 12, 12))

            painter.setPen(QPen(QColor(COLORS['text_secondary']), 1))
            painter.setFont(QFont("Arial", 8))
            percent = (value / total) * 100
            legend_text = f"{label} ({percent:.1f}%)"
            painter.drawText(QRectF(legend_rect.x() + 16, legend_y - 2, legend_rect.width() - 16, 16),
                             Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, legend_text)
            legend_y += 20

        # Draw total value in center
        painter.setPen(QPen(QColor(COLORS['text_primary']), 1))
        painter.setFont(QFont("Arial", 12, QFont.Weight.Bold))
        painter.drawText(pie_rect, Qt.AlignmentFlag.AlignCenter, f"Total\n{int(total)}")