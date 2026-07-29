# -*- coding: utf-8 -*-
"""
HomePage - Workspace Launcher for CenterManager.
"""
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QSizePolicy, QScrollArea
)

from centermanager.ui.design_system.tokens import COLORS


class WorkspaceButton(QFrame):
    """Button-like card for launching a workspace."""
    clicked = Signal(str)

    def __init__(
        self,
        workspace_id: str,
        name: str,
        icon: str,
        description: str = "",
        disabled: bool = False,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._workspace_id = workspace_id
        self._disabled = disabled
        self._setup_ui(name, icon, description)

    def _setup_ui(self, name: str, icon: str, description: str) -> None:
        self.setFrameStyle(QFrame.Shape.NoFrame)
        opacity = "0.5" if self._disabled else "1"
        background = "#f5f5f5" if self._disabled else "white"
        # Sử dụng màu gray_100 thay vì gray_50 (không tồn tại)
        hover_bg = COLORS['gray_100']
        self.setStyleSheet(f"""
            QFrame {{
                background: {background};
                border-radius: 12px;
                border: 1px solid {COLORS['gray_200']};
                padding: 16px;
                opacity: {opacity};
            }}
            QFrame:hover {{
                background: {hover_bg};
                border-color: {COLORS['primary']};
                cursor: pointer;
            }}
        """)
        self.setFixedHeight(120)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)

        icon_label = QLabel(icon)
        icon_label.setStyleSheet("font-size: 32px;")
        icon_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(icon_label)

        name_label = QLabel(name)
        name_label.setStyleSheet(f"""
            font-size: 16px;
            font-weight: 600;
            color: {COLORS['text_primary']};
        """)
        name_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(name_label)

        if description:
            desc_label = QLabel(description)
            desc_label.setStyleSheet(f"""
                font-size: 12px;
                color: {COLORS['muted']};
            """)
            desc_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            desc_label.setWordWrap(True)
            layout.addWidget(desc_label)

        if self._disabled:
            self.setToolTip("Coming soon")
        else:
            self.setCursor(Qt.CursorShape.PointingHandCursor)

    def mousePressEvent(self, event) -> None:
        if not self._disabled:
            self.clicked.emit(self._workspace_id)
        super().mousePressEvent(event)


class HomePage(QWidget):
    """Workspace Launcher - Home Page of CenterManager."""

    workspace_selected = Signal(str)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 40, 40, 40)
        layout.setSpacing(24)

        # Header
        header = QLabel("🏛️ CenterManager")
        header.setStyleSheet(f"""
            font-size: 28px;
            font-weight: 700;
            color: {COLORS['primary']};
        """)
        header.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(header)

        subtitle = QLabel("Select a workspace to begin")
        subtitle.setStyleSheet(f"""
            font-size: 16px;
            color: {COLORS['muted']};
        """)
        subtitle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(subtitle)

        # Workspace grid
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        grid_layout = QGridLayout(container)
        grid_layout.setSpacing(16)
        grid_layout.setContentsMargins(0, 0, 0, 0)

        workspaces = [
            ("student", "👨‍🎓 Student Workspace", "Manage students, parents, assessments", False),
            ("teacher", "👨‍🏫 Teacher Workspace", "Teaching activities and classes", True),
            ("finance", "💰 Finance Workspace", "Invoices, payments, revenue", True),
            ("hr", "👥 Human Resources", "Employees, teachers, payroll", True),
            ("report", "📊 Reports", "Business analytics and KPIs", True),
            ("admin", "⚙ Administration", "System configuration", True),
        ]

        row, col = 0, 0
        for ws_id, name, desc, disabled in workspaces:
            # Lấy icon từ tên (phần emoji trước khoảng trắng)
            icon = name.split()[0] if name.split() else "📌"
            btn = WorkspaceButton(ws_id, name, icon, desc, disabled)
            if not disabled:
                btn.clicked.connect(self._on_workspace_clicked)
            grid_layout.addWidget(btn, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        footer = QLabel("© 2026 CenterManager v0.1.0")
        footer.setStyleSheet(f"""
            color: {COLORS['gray_400']};
            font-size: 12px;
        """)
        footer.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(footer)

    def _on_workspace_clicked(self, workspace_id: str) -> None:
        self.workspace_selected.emit(workspace_id)