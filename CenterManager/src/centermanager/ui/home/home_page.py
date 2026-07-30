# -*- coding: utf-8 -*-
"""
HomePage - Workspace Launcher for CenterManager.
This page only displays workspace cards and allows navigation.
No business logic or dashboard data is shown here.
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
        header = QLabel("🏛️ CenterManager")
        header.setStyleSheet(f"""
            font-size: 28px;
            font-weight: 700;
            color: {COLORS['primary']};
        """)
        header.setAlignment(Qt.AlignCenter)
        container_layout.addWidget(header)

        subtitle = QLabel("Your education center command center")
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
            self.workspace_grid.addWidget(card, row, col)
            col += 1
            if col >= 2:
                col = 0
                row += 1

    def _on_workspace_clicked(self, workspace_id: str) -> None:
        self.workspace_selected.emit(workspace_id)