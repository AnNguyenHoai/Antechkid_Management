# -*- coding: utf-8 -*-
"""
HomePage - Command Center / Workspace Launcher for CenterManager.
Now with permission-based workspace filtering.
"""
import logging
from typing import Optional, List

from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QScrollArea,
    QLabel, QFrame, QSizePolicy, QPushButton, QListWidget, QListWidgetItem
)

from centermanager.services.home_dashboard_service import HomeDashboardService
from centermanager.ui.design_system.tokens import COLORS, SPACING, TYPOGRAPHY
from centermanager.ui.design_system.components import SectionHeader, EmptyState, SecondaryButton
from centermanager.ui.home.workspace_card import WorkspaceCard
from centermanager.ui.home.activity_item import ActivityItem
from centermanager.core.current_user import get_current_user
from centermanager.services.permission_service import PermissionService
from centermanager.database.engine import create_production_engine
from sqlalchemy.orm import sessionmaker

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
        self._current_user = get_current_user()
        
        # Initialize permission service
        engine = create_production_engine()
        session_factory = sessionmaker(bind=engine)
        self._permission_service = PermissionService(session_factory)
        
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        self.setStyleSheet("background-color: #f5f7fa;")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        main_scroll = QScrollArea()
        main_scroll.setWidgetResizable(True)
        main_scroll.setFrameShape(QFrame.Shape.NoFrame)
        main_scroll.setStyleSheet("background: transparent; border: none;")

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

        container_layout.addSpacing(8)

        # Workspace cards
        self.workspace_grid = QGridLayout()
        self.workspace_grid.setSpacing(16)
        self.workspace_grid.setContentsMargins(0, 0, 0, 0)
        container_layout.addLayout(self.workspace_grid)

        # Two-column layout
        main_content = QHBoxLayout()
        main_content.setSpacing(24)

        # Left column
        left_col = QVBoxLayout()
        left_col.setSpacing(24)

        # ---- Recent Activities using QListWidget ----
        self.recent_section = QWidget()
        recent_layout = QVBoxLayout(self.recent_section)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(8)
        recent_header = SectionHeader("Recent Activities", subtitle="Latest across all workspaces")
        recent_layout.addWidget(recent_header)

        self.recent_list = QListWidget()
        self.recent_list.setVerticalScrollMode(QListWidget.ScrollMode.ScrollPerPixel)
        self.recent_list.setUniformItemSizes(True)
        self.recent_list.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.recent_list.setStyleSheet("""
            QListWidget {
                border: 1px solid #e0e0e0;
                border-radius: 8px;
                background: #ffffff;
                outline: none;
            }
            QListWidget::item {
                padding: 0px;
                border-bottom: 1px solid #f0f0f0;
            }
            QScrollBar:vertical {
                border: none;
                background: #f1f1f1;
                width: 8px;
                margin: 0px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical {
                background: #c1c1c1;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #a8a8a8;
            }
        """)
        self.recent_list.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.recent_list.setFixedHeight(400)
        self.recent_list.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        recent_layout.addWidget(self.recent_list)

        left_col.addWidget(self.recent_section)

        # Today Summary
        self.today_section = QWidget()
        today_layout = QVBoxLayout(self.today_section)
        today_layout.setContentsMargins(0, 0, 0, 0)
        today_layout.setSpacing(8)
        today_header = SectionHeader("Today's Summary")
        today_layout.addWidget(today_header)
        self.today_container = QWidget()
        self.today_container_layout = QVBoxLayout(self.today_container)
        self.today_container_layout.setContentsMargins(0, 0, 0, 0)
        self.today_container_layout.setSpacing(4)
        today_layout.addWidget(self.today_container)
        left_col.addWidget(self.today_section)

        left_col.addStretch()
        main_content.addLayout(left_col, 2)

        # Right column: System Status
        right_col = QVBoxLayout()
        right_col.setSpacing(24)
        self.status_section = QWidget()
        status_layout = QVBoxLayout(self.status_section)
        status_layout.setContentsMargins(0, 0, 0, 0)
        status_layout.setSpacing(8)
        status_header = SectionHeader("System Status")
        status_layout.addWidget(status_header)
        self.status_container = QWidget()
        self.status_container_layout = QVBoxLayout(self.status_container)
        self.status_container_layout.setContentsMargins(0, 0, 0, 0)
        self.status_container_layout.setSpacing(4)
        status_layout.addWidget(self.status_container)
        right_col.addWidget(self.status_section)
        right_col.addStretch()
        main_content.addLayout(right_col, 1)

        container_layout.addLayout(main_content)
        container_layout.addStretch()

        main_scroll.setWidget(container)
        layout.addWidget(main_scroll)

    def refresh(self) -> None:
        self._populate_workspace_cards()
        self._populate_recent_activities()
        self._populate_today_summary()
        self._populate_system_status()

    def _populate_workspace_cards(self) -> None:
        """Populate workspace cards with permission filtering."""
        while self.workspace_grid.count():
            item = self.workspace_grid.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Get all workspace summaries
        all_summaries = self._service.get_workspace_summaries()

        # Filter by permission
        permission_map = {
            "student": None,  # Always visible
            "teacher": "teacher.view",
            "finance": "finance.view",
        }

        filtered_summaries = []
        for ws in all_summaries:
            required_perm = permission_map.get(ws.workspace_id)
            if required_perm is None:
                filtered_summaries.append(ws)
            elif self._permission_service.has_permission(required_perm):
                filtered_summaries.append(ws)

        row, col = 0, 0
        for ws in filtered_summaries:
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

    def _populate_recent_activities(self) -> None:
        self.recent_list.clear()
        activities = self._service.get_recent_activities(limit=30)

        if activities:
            for act in activities:
                item_widget = ActivityItem(
                    icon=act.icon,
                    title=act.title,
                    student_name=act.student_name,
                    student_code=act.student_code,
                    time=act.time
                )
                item_widget.setFixedHeight(70)
                list_item = QListWidgetItem()
                list_item.setSizeHint(QSize(0, 70))
                self.recent_list.addItem(list_item)
                self.recent_list.setItemWidget(list_item, item_widget)
        else:
            empty = EmptyState(
                icon="📭",
                title="No recent activities",
                description="Activities will appear here as you use the system."
            )
            empty.setFixedHeight(200)
            list_item = QListWidgetItem()
            list_item.setSizeHint(QSize(0, 200))
            self.recent_list.addItem(list_item)
            self.recent_list.setItemWidget(list_item, empty)

        self.recent_list.updateGeometry()
        self.recent_list.repaint()

    def _populate_today_summary(self) -> None:
        self._clear_layout(self.today_container_layout)
        summary = self._service.get_today_summary()
        items = [
            (f"📚 {summary.today_classes} classes today", "Scheduled classes"),
            (f"📊 {summary.today_assessments} assessments today", "Assessments recorded"),
            (f"🎂 {len(summary.today_birthdays)} birthdays today", ", ".join(summary.today_birthdays) if summary.today_birthdays else "None"),
            (f"📅 {summary.upcoming_sessions} upcoming sessions", "Next 7 days"),
            (f"⚠️ {len(summary.pending_tasks)} pending tasks", "Students needing attention"),
        ]
        for label, detail in items:
            widget = QWidget()
            layout = QHBoxLayout(widget)
            layout.setContentsMargins(0, 2, 0, 2)
            label_w = QLabel(label)
            label_w.setStyleSheet(f"font-size: 14px; font-weight: 500; color: {COLORS['text_primary']};")
            detail_w = QLabel(detail)
            detail_w.setStyleSheet(f"font-size: 12px; color: {COLORS['muted']};")
            layout.addWidget(label_w)
            layout.addWidget(detail_w)
            layout.addStretch()
            self.today_container_layout.addWidget(widget)

    def _populate_system_status(self) -> None:
        self._clear_layout(self.status_container_layout)
        status = self._service.get_system_status()
        items = [
            (f"🟢 Database: {status.database_status}", ""),
            (f"📦 Version: {status.version}", ""),
            (f"💾 Last backup: {status.last_backup}", ""),
            (f"👤 User: {status.current_user}", ""),
            (f"🌍 Environment: {status.environment}", ""),
        ]
        for label, _ in items:
            label_w = QLabel(label)
            label_w.setStyleSheet(f"font-size: 13px; color: {COLORS['text_secondary']}; padding: 2px 0;")
            self.status_container_layout.addWidget(label_w)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def _on_workspace_clicked(self, workspace_id: str) -> None:
        self.workspace_selected.emit(workspace_id)