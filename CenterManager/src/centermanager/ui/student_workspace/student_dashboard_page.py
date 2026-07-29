# -*- coding: utf-8 -*-
"""
StudentDashboardPage - redesigned dashboard using design system components.
"""
import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal, QTimer
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QScrollArea, QFrame,
    QGridLayout
)

from centermanager.services.student_dashboard_service import StudentDashboardService
from centermanager.ui.design_system import (
    StatisticCard, ActivityCard, SectionHeader, EmptyState,
    PrimaryButton, SecondaryButton
)
from centermanager.ui.design_system.tokens import SPACING, COLORS

logger = logging.getLogger(__name__)


class StudentDashboardPage(QWidget):
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
        QTimer.singleShot(100, self.refresh)

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet(f"background: {COLORS['background']};")

        container = QWidget()
        container.setStyleSheet(f"background: {COLORS['background']};")
        container_layout = QVBoxLayout(container)
        # Giảm padding từ xl (24) xuống md (12)
        container_layout.setContentsMargins(SPACING['md'], SPACING['md'], SPACING['md'], SPACING['md'])
        container_layout.setSpacing(SPACING['lg'])

        # Stats grid
        self.stats_grid = QGridLayout()
        self.stats_grid.setSpacing(SPACING['sm'])
        self.stats_grid.setContentsMargins(0, 0, 0, 0)

        self.stat_cards = []
        stat_data = [
            ("👥", "Total Students", "0"),
            ("✅", "Active", "0"),
            ("📦", "Archived", "0"),
            ("🌟", "New This Month", "0"),
        ]
        for i, (icon, label, default) in enumerate(stat_data):
            card = StatisticCard(icon, label, default)
            # Đảm bảo card có kích thước đủ lớn
            card.setMinimumHeight(80)
            self.stat_cards.append(card)
            self.stats_grid.addWidget(card, i // 2, i % 2)
        container_layout.addLayout(self.stats_grid)

        # Recent Activities
        self.recent_section = QWidget()
        recent_layout = QVBoxLayout(self.recent_section)
        recent_layout.setContentsMargins(0, 0, 0, 0)
        recent_layout.setSpacing(SPACING['sm'])

        header = SectionHeader(
            "Recent Activities",
            subtitle="Latest timeline events",
            action_text="View All",
            action_callback=lambda: None
        )
        recent_layout.addWidget(header)

        self.recent_container = QWidget()
        self.recent_container_layout = QVBoxLayout(self.recent_container)
        self.recent_container_layout.setContentsMargins(0, 0, 0, 0)
        self.recent_container_layout.setSpacing(0)
        recent_layout.addWidget(self.recent_container)
        container_layout.addWidget(self.recent_section)

        # Students Requiring Attention
        self.attention_section = QWidget()
        attention_layout = QVBoxLayout(self.attention_section)
        attention_layout.setContentsMargins(0, 0, 0, 0)
        attention_layout.setSpacing(SPACING['sm'])

        att_header = SectionHeader(
            "Students Requiring Attention",
            subtitle="Students needing follow-up"
        )
        attention_layout.addWidget(att_header)

        self.attention_container = QWidget()
        self.attention_container_layout = QVBoxLayout(self.attention_container)
        self.attention_container_layout.setContentsMargins(0, 0, 0, 0)
        self.attention_container_layout.setSpacing(SPACING['xs'])
        attention_layout.addWidget(self.attention_container)
        container_layout.addWidget(self.attention_section)

        # Quick Actions
        actions_section = QWidget()
        actions_layout = QHBoxLayout(actions_section)
        actions_layout.setContentsMargins(0, 0, 0, 0)
        actions_layout.setSpacing(SPACING['sm'])

        add_btn = PrimaryButton("➕ Add Student")
        add_btn.clicked.connect(self.add_student_clicked.emit)
        import_btn = SecondaryButton("📥 Import")
        import_btn.clicked.connect(self.import_students_clicked.emit)
        export_btn = SecondaryButton("📤 Export")
        export_btn.clicked.connect(self.export_students_clicked.emit)

        actions_layout.addWidget(add_btn)
        actions_layout.addWidget(import_btn)
        actions_layout.addWidget(export_btn)
        actions_layout.addStretch()
        container_layout.addWidget(actions_section)

        container_layout.addStretch()

        scroll.setWidget(container)
        layout.addWidget(scroll)

    def refresh(self) -> None:
        logger.debug("Refreshing dashboard...")
        try:
            stats = self._service.get_stats()
            logger.info(f"Dashboard stats: total={stats.total}, active={stats.active}, archived={stats.archived}, new={stats.new_this_month}")
            self.stat_cards[0].set_value(str(stats.total))
            self.stat_cards[1].set_value(str(stats.active))
            self.stat_cards[2].set_value(str(stats.archived))
            self.stat_cards[3].set_value(str(stats.new_this_month))
        except Exception as e:
            logger.exception("Failed to get dashboard stats")

        self._clear_layout(self.recent_container_layout)
        try:
            activities = self._service.get_recent_activities(limit=8)
            if activities:
                for act in activities:
                    card = ActivityCard(
                        icon="📌",
                        title=act.title,
                        student_name=act.student_name,
                        student_code=act.student_code,
                        time=act.time
                    )
                    self.recent_container_layout.addWidget(card)
            else:
                empty = EmptyState(
                    icon="📭",
                    title="No recent activities",
                    description="Activities will appear here when students are updated."
                )
                self.recent_container_layout.addWidget(empty)
        except Exception as e:
            logger.exception("Failed to load recent activities")

        self._clear_layout(self.attention_container_layout)
        try:
            attention = self._service.get_students_requiring_attention()
            if attention:
                for item in attention:
                    btn = SecondaryButton(
                        f"⚠️ {item.full_name} ({item.student_code}) – {item.reason}"
                    )
                    btn.setStyleSheet(btn.styleSheet() + """
                        QPushButton {
                            text-align: left;
                            padding: 8px 12px;
                            background: #fff3e0;
                            border-color: #ffe0b2;
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
        except Exception as e:
            logger.exception("Failed to load attention students")

    def _clear_layout(self, layout) -> None:
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()