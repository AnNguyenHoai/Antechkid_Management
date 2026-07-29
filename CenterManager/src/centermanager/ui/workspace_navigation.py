# -*- coding: utf-8 -*-
"""
WorkspaceNavigation - sidebar navigation for a workspace.
"""
from typing import Optional, List, Dict

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QPushButton, QLabel, QFrame,
    QScrollArea, QSizePolicy
)

from centermanager.ui.design_system.tokens import COLORS


class NavItem(QPushButton):
    """Navigation menu item with icon and label."""
    clicked_signal = Signal(str)

    def __init__(
        self,
        page_id: str,
        icon: str,
        label: str,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._page_id = page_id
        self._setup_ui(icon, label)

    def _setup_ui(self, icon: str, label: str) -> None:
        self.setText(f"{icon}  {label}")
        self.setStyleSheet(f"""
            QPushButton {{
                text-align: left;
                padding: 8px 12px;
                border: none;
                border-radius: 6px;
                background: transparent;
                font-size: 14px;
                color: {COLORS['text_secondary']};
            }}
            QPushButton:hover {{
                background: #e8f0fe;
            }}
            QPushButton:checked {{
                background: #e3f2fd;
                color: {COLORS['primary']};
                font-weight: 500;
            }}
        """)
        self.setCheckable(True)
        self.setAutoExclusive(True)
        self.setFixedHeight(40)
        self.clicked.connect(lambda: self.clicked_signal.emit(self._page_id))


class WorkspaceNavigation(QWidget):
    """Sidebar navigation for a workspace."""
    page_selected = Signal(str)

    def __init__(
        self,
        workspace_name: str,
        pages: List[Dict[str, str]],
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._pages = pages
        self._setup_ui(workspace_name)

    def _setup_ui(self, workspace_name: str) -> None:
        self.setStyleSheet(f"""
            QWidget {{
                background: white;
                border-right: 1px solid {COLORS['gray_200']};
            }}
        """)
        self.setFixedWidth(220)
        self.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Expanding)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Workspace header
        header = QWidget()
        header.setStyleSheet(f"""
            background: {COLORS['gray_100']};
            padding: 12px 16px;
            border-bottom: 1px solid {COLORS['gray_200']};
        """)
        header_layout = QVBoxLayout(header)
        header_layout.setSpacing(2)
        ws_label = QLabel(workspace_name)
        ws_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        """)
        header_layout.addWidget(ws_label)
        sub_label = QLabel("Navigation")
        sub_label.setStyleSheet(f"""
            font-size: 12px;
            color: {COLORS['muted']};
        """)
        header_layout.addWidget(sub_label)
        layout.addWidget(header)

        # Pages
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")
        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(2)

        self._buttons = []
        for page in self._pages:
            btn = NavItem(page["id"], page["icon"], page["label"])
            btn.clicked_signal.connect(self._on_page_clicked)
            container_layout.addWidget(btn)
            self._buttons.append(btn)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def _on_page_clicked(self, page_id: str) -> None:
        self.page_selected.emit(page_id)

    def set_active_page(self, page_id: str) -> None:
        for btn in self._buttons:
            if btn._page_id == page_id:
                btn.setChecked(True)
                break