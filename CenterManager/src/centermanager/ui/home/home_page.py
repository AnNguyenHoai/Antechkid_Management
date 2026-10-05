# -*- coding: utf-8 -*-
"""Home Dashboard V3 for CenterManager.

The Home surface is an operational landing page, not a second application shell.
It consumes only permission-filtered ``WorkspaceSummary`` objects from
``HomeDashboardService`` and keeps navigation ownership in ``workspace_selected``.
V3 changes presentation only: Today, Attention, Quick access, then the workspace
launcher. No business metric is invented outside the service projection.
"""
from __future__ import annotations

import logging
from typing import Iterable, Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from centermanager.services.home_dashboard_service import HomeDashboardService, WorkspaceSummary
from centermanager.ui.design_system.foundation import Button, ButtonVariant, ComponentSize, EmptyState, ErrorState
from centermanager.ui.design_system.tokens import (
    COLORS,
    COMPONENT_METRICS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    TYPOGRAPHY,
)
from centermanager.ui.home.workspace_card import WorkspaceCard

logger = logging.getLogger(__name__)


class _TodayPanel(QFrame):
    """Service-derived operational summary; intentionally contains no synthetic KPI."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeTodayPanel")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(176)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING["xl"], SPACING["xl"], SPACING["xl"], SPACING["xl"])
        layout.setSpacing(SPACING["sm"])

        eyebrow = QLabel("TODAY", self)
        eyebrow.setObjectName("HomePanelEyebrow")
        self.headline = QLabel("Your center is ready", self)
        self.headline.setObjectName("HomeTodayHeadline")
        self.headline.setWordWrap(True)
        self.detail = QLabel("", self)
        self.detail.setObjectName("HomeTodayDetail")
        self.detail.setWordWrap(True)

        layout.addWidget(eyebrow)
        layout.addWidget(self.headline)
        layout.addWidget(self.detail)
        layout.addStretch()
        self.setStyleSheet(
            f"""
            QFrame#HomeTodayPanel {{
                background-color: {COLORS["surface_card"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
            }}
            QLabel#HomePanelEyebrow {{
                color: {COLORS["action_accent"]}; font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["badge"]}px; font-weight: {FONT_WEIGHTS["bold"]};
                border: none;
            }}
            QLabel#HomeTodayHeadline {{
                color: {COLORS["text_primary"]}; font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["section_title"]}px; font-weight: {FONT_WEIGHTS["bold"]};
                border: none;
            }}
            QLabel#HomeTodayDetail {{
                color: {COLORS["text_secondary"]}; font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body"]}px; font-weight: {FONT_WEIGHTS["regular"]};
                border: none;
            }}
            """
        )

    def update_from(self, summaries: Iterable[WorkspaceSummary]) -> None:
        summaries = list(summaries)
        attention = sum(1 for item in summaries if item.health_status in {"warning", "critical"})
        self.headline.setText("Your center is ready" if attention == 0 else "There is work to review")
        if attention == 0:
            self.detail.setText(f"{len(summaries)} available workspace(s), with no reported attention state.")
        else:
            self.detail.setText(f"{len(summaries)} available workspace(s) · {attention} reporting attention.")


class HomePage(QWidget):
    """Modern operational landing page backed by ``HomeDashboardService``."""

    workspace_selected = Signal(str)

    def __init__(self, home_service: HomeDashboardService, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._service = home_service
        self._cards: list[WorkspaceCard] = []
        self._state_widget: Optional[QWidget] = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        self.setObjectName("HomeDashboardV3")
        self.setStyleSheet(f"QWidget#HomeDashboardV3 {{ background-color: {COLORS['surface_app']}; }}")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("HomeDashboardScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(f"QScrollArea#HomeDashboardScrollArea {{ background-color: {COLORS['surface_app']}; border: none; }}")
        root.addWidget(self.scroll_area)

        self.container = QWidget(self.scroll_area)
        self.container.setObjectName("HomeDashboardContent")
        self.container.setStyleSheet(f"QWidget#HomeDashboardContent {{ background-color: {COLORS['surface_app']}; }}")
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(SPACING["xxl"], SPACING["xl"], SPACING["xxl"], SPACING["xxl"])
        self.container_layout.setSpacing(SPACING["xl"])
        self.scroll_area.setWidget(self.container)

        self._build_header()
        self._build_dashboard_content()

        self.state_host = QWidget(self.container)
        self.state_layout = QVBoxLayout(self.state_host)
        self.state_layout.setContentsMargins(0, SPACING["xl"], 0, 0)
        self.state_host.setVisible(False)
        self.container_layout.addWidget(self.state_host, 1)
        self.container_layout.addStretch()

    def _build_header(self) -> None:
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACING["lg"])
        copy_layout = QVBoxLayout()
        copy_layout.setSpacing(SPACING["xs"])
        eyebrow = QLabel("HOME", self.container)
        eyebrow.setObjectName("HomeEyebrow")
        title = QLabel("Center overview", self.container)
        title.setObjectName("HomeTitle")
        subtitle = QLabel("See what needs attention, then jump back into your work.", self.container)
        subtitle.setObjectName("HomeSubtitle")
        subtitle.setWordWrap(True)
        copy_layout.addWidget(eyebrow)
        copy_layout.addWidget(title)
        copy_layout.addWidget(subtitle)
        header_layout.addLayout(copy_layout, 1)

        self.refresh_button = Button("Refresh", variant=ButtonVariant.SECONDARY, size=ComponentSize.SMALL, parent=self.container)
        self.refresh_button.setToolTip("Refresh dashboard data")
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        header_layout.addWidget(self.refresh_button, alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        header = QWidget(self.container)
        header.setLayout(header_layout)
        header.setStyleSheet(
            f"""
            QLabel#HomeEyebrow {{ color: {COLORS["action_accent"]}; font-family: {FONT_FAMILY}; font-size: {TYPOGRAPHY["badge"]}px; font-weight: {FONT_WEIGHTS["bold"]}; }}
            QLabel#HomeTitle {{ color: {COLORS["text_primary"]}; font-family: {FONT_FAMILY}; font-size: {TYPOGRAPHY["page_title"]}px; font-weight: {FONT_WEIGHTS["bold"]}; }}
            QLabel#HomeSubtitle {{ color: {COLORS["text_muted"]}; font-family: {FONT_FAMILY}; font-size: {TYPOGRAPHY["body"]}px; font-weight: {FONT_WEIGHTS["regular"]}; }}
            """
        )
        self.container_layout.addWidget(header)

    def _build_dashboard_content(self) -> None:
        self.dashboard_content = QWidget(self.container)
        content = QVBoxLayout(self.dashboard_content)
        content.setContentsMargins(0, 0, 0, 0)
        content.setSpacing(SPACING["xl"])

        overview = QHBoxLayout()
        overview.setSpacing(SPACING["md"])
        self.today_panel = _TodayPanel(self.dashboard_content)
        overview.addWidget(self.today_panel, 2)

        side = QVBoxLayout()
        side.setSpacing(SPACING["md"])
        self.attention_panel = self._build_info_panel("ATTENTION", "Nothing needs attention.", "HomeAttentionPanel")
        self.quick_panel = self._build_info_panel("QUICK ACCESS", "Choose a workspace below to continue.", "HomeQuickPanel")
        side.addWidget(self.attention_panel)
        side.addWidget(self.quick_panel)
        overview.addLayout(side, 1)
        content.addLayout(overview)

        launcher_header = QVBoxLayout()
        launcher_header.setSpacing(SPACING["xs"])
        workspace_title = QLabel("Workspace launcher", self.dashboard_content)
        workspace_title.setObjectName("HomeSectionTitle")
        workspace_help = QLabel("Only workspaces available to your account are shown.", self.dashboard_content)
        workspace_help.setObjectName("HomeSectionHelp")
        launcher_header.addWidget(workspace_title)
        launcher_header.addWidget(workspace_help)
        content.addLayout(launcher_header)

        self.workspace_grid = QGridLayout()
        self.workspace_grid.setHorizontalSpacing(SPACING["md"])
        self.workspace_grid.setVerticalSpacing(SPACING["md"])
        for column in range(3):
            self.workspace_grid.setColumnStretch(column, 1)
        content.addLayout(self.workspace_grid)
        self.dashboard_content.setStyleSheet(
            f"""
            QLabel#HomeSectionTitle {{ color: {COLORS["text_primary"]}; font-family: {FONT_FAMILY}; font-size: {TYPOGRAPHY["section_title"]}px; font-weight: {FONT_WEIGHTS["semibold"]}; }}
            QLabel#HomeSectionHelp {{ color: {COLORS["text_muted"]}; font-family: {FONT_FAMILY}; font-size: {TYPOGRAPHY["body_small"]}px; font-weight: {FONT_WEIGHTS["regular"]}; }}
            """
        )
        self.container_layout.addWidget(self.dashboard_content)

    def _build_info_panel(self, title: str, text: str, object_name: str) -> QFrame:
        panel = QFrame(self.dashboard_content)
        panel.setObjectName(object_name)
        panel.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"])
        layout.setSpacing(SPACING["xs"])
        label = QLabel(title, panel)
        label.setObjectName("HomeInfoTitle")
        detail = QLabel(text, panel)
        detail.setObjectName("HomeInfoDetail")
        detail.setWordWrap(True)
        layout.addWidget(label)
        layout.addWidget(detail)
        layout.addStretch()
        panel.detail_label = detail
        panel.setStyleSheet(
            f"""
            QFrame#{object_name} {{ background-color: {COLORS["surface_card"]}; border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]}; border-radius: {RADIUS["lg"]}px; }}
            QLabel#HomeInfoTitle {{ color: {COLORS["text_muted"]}; font-family: {FONT_FAMILY}; font-size: {TYPOGRAPHY["badge"]}px; font-weight: {FONT_WEIGHTS["bold"]}; border: none; }}
            QLabel#HomeInfoDetail {{ color: {COLORS["text_secondary"]}; font-family: {FONT_FAMILY}; font-size: {TYPOGRAPHY["body_small"]}px; font-weight: {FONT_WEIGHTS["regular"]}; border: none; }}
            """
        )
        return panel

    def _on_refresh_clicked(self) -> None:
        self.refresh(force=True)

    def refresh(self, *, force: bool = False) -> None:
        try:
            if force and hasattr(self._service, "refresh"):
                self._service.refresh()
            self._populate_workspace_cards()
        except Exception:
            logger.exception("Failed to refresh Home Dashboard V3")
            self._show_error_state()

    def _populate_workspace_cards(self) -> None:
        summaries = list(self._service.get_workspace_summaries())
        self._clear_workspace_grid()
        if not summaries:
            self._show_empty_state()
            return

        self._render_overview(summaries)
        for index, summary in enumerate(summaries):
            card = WorkspaceCard(
                workspace_id=summary.workspace_id,
                name=summary.name,
                icon=summary.icon,
                description=summary.description,
                summary_text=summary.summary_text,
                health_status=summary.health_status,
                health_details=summary.health_details,
                quick_action_label=summary.quick_action_label,
                parent=self.dashboard_content,
            )
            card.clicked.connect(self._on_workspace_clicked)
            self._cards.append(card)
            self.workspace_grid.addWidget(card, index // 3, index % 3)
        self._show_dashboard_content()

    def _render_overview(self, summaries: Iterable[WorkspaceSummary]) -> None:
        summaries = list(summaries)
        self.today_panel.update_from(summaries)
        attention_items = [item for item in summaries if item.health_status in {"warning", "critical"}]
        if attention_items:
            messages = []
            for item in attention_items:
                detail = item.health_details.strip() or "Review this workspace"
                messages.append(f"{item.name}: {detail}")
            self.attention_panel.detail_label.setText("\n".join(messages))
        else:
            self.attention_panel.detail_label.setText("Nothing needs attention.")
        self.quick_panel.detail_label.setText(f"{len(summaries)} workspace(s) available. Choose one below to continue.")

    def _clear_workspace_grid(self) -> None:
        self._cards.clear()
        while self.workspace_grid.count():
            item = self.workspace_grid.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _clear_state(self) -> None:
        if self._state_widget is None:
            return
        self.state_layout.removeWidget(self._state_widget)
        self._state_widget.deleteLater()
        self._state_widget = None

    def _show_dashboard_content(self) -> None:
        self._clear_state()
        self.state_host.setVisible(False)
        self.dashboard_content.setVisible(True)

    def _show_empty_state(self) -> None:
        self.dashboard_content.setVisible(False)
        self._clear_state()
        self._state_widget = EmptyState(icon=None, title="No workspaces available", description="No operational areas are available for the current account.", parent=self.state_host)
        self.state_layout.addWidget(self._state_widget)
        self.state_host.setVisible(True)

    def _show_error_state(self) -> None:
        self.dashboard_content.setVisible(False)
        self._clear_state()
        self._state_widget = ErrorState(title="Dashboard unavailable", description="Center overview could not be loaded. Try refreshing the data.", retry_text="Try again", retry_callback=self._on_refresh_clicked, parent=self.state_host)
        self.state_layout.addWidget(self._state_widget)
        self.state_host.setVisible(True)

    def _on_workspace_clicked(self, workspace_id: str) -> None:
        self.workspace_selected.emit(workspace_id)
