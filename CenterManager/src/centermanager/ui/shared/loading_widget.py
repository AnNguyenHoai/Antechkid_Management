# -*- coding: utf-8 -*-
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QWidget, QVBoxLayout, QFrame, QSizePolicy

from centermanager.ui.design_system.tokens import COLORS, SPACING


class LoadingSkeleton(QFrame):
    """A simple skeleton loading card."""
    def __init__(self, height: int = 60, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.NoFrame)
        self.setStyleSheet(f"""
            QFrame {{
                background: {COLORS['gray_100']};
                border-radius: 4px;
                margin: {SPACING['xs']}px 0;
            }}
        """)
        self.setFixedHeight(height)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)


class LoadingWidget(QWidget):
    """Widget with multiple skeleton lines."""
    def __init__(self, count: int = 5, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(SPACING['xs'])
        for _ in range(count):
            layout.addWidget(LoadingSkeleton())
        self.setVisible(True)