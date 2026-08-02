# src/centermanager/ui/home/home_page.py
# -*- coding: utf-8 -*-
"""
HomePage - Workspace Launcher for CenterManager.
All workspace cards have equal size and expand to fit window.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QGridLayout, QScrollArea,
    QLabel, QFrame, QSizePolicy
)

from centermanager.services.home_dashboard_service import HomeDashboardService
from centermanager.ui.home.workspace_card import WorkspaceCard
from centermanager.ui.design_system.tokens import COLORS

logger = logging.getLogger(__name__)


class HomePage(QWidget):
    workspace_selected = Signal(str)

    def __init__(
        self,
        home_service: HomeDashboardService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = home_service
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        self.setStyleSheet(f"background-color: {COLORS['background']};")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: transparent; border: none;")

        container = QWidget()
        container.setStyleSheet("background: transparent;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(40, 40, 40, 40)
        container_layout.setSpacing(24)

        # Header
        header = QLabel("AN TECHKIDS")
        header.setStyleSheet(f"""
            font-size: 28px;
            font-weight: 700;
            color: {COLORS['primary']};
        """)
        header.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(header)

        subtitle = QLabel("CHẠM CÔNG NGHỆ - MỞ TƯƠNG LAI")
        subtitle.setStyleSheet(f"""
            font-size: 16px;
            color: {COLORS['muted']};
        """)
        subtitle.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(subtitle)

        container_layout.addSpacing(16)

        # Workspace cards grid
        self.workspace_grid = QGridLayout()
        self.workspace_grid.setSpacing(16)
        self.workspace_grid.setContentsMargins(0, 0, 0, 0)
        # Make columns stretch equally
        self.workspace_grid.setColumnStretch(0, 1)
        self.workspace_grid.setColumnStretch(1, 1)
        container_layout.addLayout(self.workspace_grid)

        container_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        """Refresh workspace cards."""
        self._populate_workspace_cards()

    def _populate_workspace_cards(self) -> None:
        # Clear grid
        while self.workspace_grid.count():
            item = self.workspace_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        summaries = self._service.get_workspace_summaries()
        row, col = 0, 0
        for ws in summaries:
            card = WorkspaceCard(
                workspace_id=ws.workspace_id,
                name=ws.name,
                icon=ws.icon,
                description=ws.description,
                summary_text=ws.summary_text,
                health_status=ws.health_status,
                health_details=ws.health_details,
                quick_action_label=ws.quick_action_label,
            )
            card.clicked.connect(self._on_workspace_clicked)
            # Cho phép card co dãn
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
            self.workspace_grid.addWidget(card, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

        # Đặt tỷ lệ co dãn cho các hàng để các card chiếm đều không gian
        for r in range(row + 1):
            self.workspace_grid.setRowStretch(r, 1)

    def _on_workspace_clicked(self, workspace_id: str) -> None:
        self.workspace_selected.emit(workspace_id)