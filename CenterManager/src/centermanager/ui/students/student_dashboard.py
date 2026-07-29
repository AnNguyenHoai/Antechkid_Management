# -*- coding: utf-8 -*-
"""
StudentDashboard - redesigned dashboard with statistics, activity feed, and actions.
"""
from typing import Optional, List

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QGridLayout, QPushButton, QLabel, QSizePolicy
)

from centermanager.services.student_dashboard_service import (
    StudentDashboardService,
    DashboardStats,
    RecentActivity,
    AttentionStudent
)
from centermanager.ui.common.statistic_card import StatisticCard
from centermanager.ui.common.activity_item import ActivityItem
from centermanager.ui.common.section_header import SectionHeader
from centermanager.ui.common.empty_state import EmptyState
from centermanager.ui import styles


class StudentDashboard(QWidget):
    """Redesigned dashboard for Student Workspace."""

    add_student_clicked = Signal()
    import_students_clicked = Signal()
    export_students_clicked = Signal()
    student_selected = Signal(int)

    def __init__(
        self,
        dashboard_service: StudentDashboardService,
        parent: Optional[QWidget] = None
    ) -> None:
        super().__init__(parent)
        self._service = dashboard_service
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Main scroll area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background: #f4f6f8;")

        container = QWidget()
        container.setStyleSheet("background: #f4f6f8;")
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(24, 24, 24, 24)
        container_layout.setSpacing(24)

        # ---- Statistics grid ----
        stats_section = QWidget()
        stats_section.setStyleSheet("background: transparent;")
        stats_layout = QGridLayout(stats_section)
        stats_layout.setSpacing(12)
        stats_layout.setContentsMargins(0, 0, 0, 0)

        # 4 stat cards
        self.stat_cards = []
        stat_data = [
            ("👥", "Total Students", "0"),
            ("✅", "Active", "0"),
            ("📦", "Archived", "0"),
            ("🌟", "New This Month", "0"),
        ]
        for i, (icon, label, default) in enumerate(stat_data):
            card = StatisticCard(icon, label, default)
            self.stat_cards.append(card)
            stats_layout.addWidget(card, i // 2, i % 2)
        container_layout.addWidget(stats_section)

        # ---- Recent Activities ----
        self.recent_section = QWidget()
        recent_layout = QVBoxLayout(self.recent_section)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(8)

        header = SectionHeader(
            "Recent Activities",
            subtitle="Latest timeline events",
            action_text="View All",
            action_callback=lambda: None  # Placeholder, can be implemented later
        )
        recent_layout.addWidget(header)

        self.recent_container = QWidget()
        self.recent_container_layout = QVBoxLayout(self.recent_container)
        self.recent_container_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_container_layout.setSpacing(0)
        recent_layout.addWidget(self.recent_container)

        container_layout.addWidget(self.recent_section)

        # ---- Students Requiring Attention ----
        self.attention_section = QWidget()
        attention_layout = QVBoxLayout(self.attention_section)
        attention_layout.setContentsMargins(0, 0, 0, 0)
        attention_layout.setSpacing(8)

        att_header = SectionHeader(
            "Students Requiring Attention",
            subtitle="Students needing follow-up"
        )
        attention_layout.addWidget(att_header)

        self.attention_container = QWidget()
        self.attention_container_layout = QVBoxLayout(self.attention_container)
        self.attention_container_layout.setContentsMargins(0, 0, 0, 0)
        self.attention_container_layout.setSpacing(4)
        attention_layout.addWidget(self.attention_container)

        container_layout.addWidget(self.attention_section)

        # ---- Quick Actions ----
        actions_section = QWidget()
        actions_layout = QHBoxLayout(actions_section)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(8)

        self.add_btn = QPushButton("➕ Add Student")
        self.add_btn.setStyleSheet(styles.BUTTON_PRIMARY)
        self.add_btn.setFixedHeight(36)
        self.add_btn.clicked.connect(self.add_student_clicked.emit)

        self.import_btn = QPushButton("📥 Import")
        self.import_btn.setStyleSheet(styles.BUTTON_SECONDARY)
        self.import_btn.setFixedHeight(36)
        self.import_btn.clicked.connect(self.import_students_clicked.emit)

        self.export_btn = QPushButton("📤 Export")
        self.export_btn.setStyleSheet(styles.BUTTON_SECONDARY)
        self.export_btn.setFixedHeight(36)
        self.export_btn.clicked.connect(self.export_students_clicked.emit)

        actions_layout.addWidget(self.add_btn)
        actions_layout.addWidget(self.import_btn)
        actions_layout.addWidget(self.export_btn)
        actions_layout.addStretch()

        container_layout.addWidget(actions_section)

        # Push everything to top
        container_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        """Reload dashboard data."""
        stats = self._service.get_stats()
        self.stat_cards[0].set_value(str(stats.total))
        self.stat_cards[1].set_value(str(stats.active))
        self.stat_cards[2].set_value(str(stats.archived))
        self.stat_cards[3].set_value(str(stats.new_this_month))

        # Recent activities
        self._clear_layout(self.recent_container_layout)
        activities = self._service.get_recent_activities(limit=8)
        if activities:
            for act in activities:
                item = ActivityItem(
                    icon="📌",
                    title=act.title,
                    student_name=act.student_name,
                    student_code=act.student_code,
                    time=act.time
                )
                self.recent_container_layout.addWidget(item)
        else:
            empty = EmptyState(
                icon="📭",
                title="No recent activities",
                description="Activities will appear here when students are updated."
            )
            self.recent_container_layout.addWidget(empty)

        # Attention students
        self._clear_layout(self.attention_container_layout)
        attention = self._service.get_students_requiring_attention()
        if attention:
            for item in attention:
                btn = QPushButton(
                    f"⚠️ {item.full_name} ({item.student_code}) – {item.reason}"
                )
                btn.setStyleSheet("""
                    QPushButton {
                        text-align: left;
                        padding: 8px 12px;
                        border: none;
                        background: #fff3e0;
                        border-radius: 4px;
                        font-size: 13px;
                    }
                    QPushButton:hover {
                        background: #ffe0b2;
                    }
                """)
                btn.clicked.connect(
                    lambda checked, sid=item.student_id: self.student_selected.emit(sid)
                )
                self.attention_container_layout.addWidget(btn)
        else:
            empty = EmptyState(
                icon="✅",
                title="All good!",
                description="No students require attention."
            )
            self.attention_container_layout.addWidget(empty)

    def _clear_layout(self, layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()