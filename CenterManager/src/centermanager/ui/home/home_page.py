# -*- coding: utf-8 -*-
"""Home Dashboard V2 for CenterManager.

The Home surface is an operational overview, not a second application shell.
It consumes permission-filtered ``WorkspaceSummary`` objects from
``HomeDashboardService`` and keeps navigation ownership in ``workspace_selected``.
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

from centermanager.services.home_dashboard_service import (
    HomeDashboardService,
    WorkspaceSummary,
)
from centermanager.ui.design_system.foundation import (
    Button,
    ButtonVariant,
    ComponentSize,
    EmptyState,
    ErrorState,
)
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


class _SnapshotTile(QFrame):
    """Compact token-driven metric used by the Home operational snapshot."""

    def __init__(self, label: str, value: str, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("HomeSnapshotTile")
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(92)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"]
        )
        layout.setSpacing(SPACING["xs"])

        self.value_label = QLabel(value, self)
        self.value_label.setObjectName("HomeSnapshotValue")
        self.label = QLabel(label, self)
        self.label.setObjectName("HomeSnapshotLabel")
        self.label.setWordWrap(True)

        layout.addWidget(self.value_label)
        layout.addWidget(self.label)

        self.setStyleSheet(
            f"""
            QFrame#HomeSnapshotTile {{
                background-color: {COLORS["surface_card"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
            }}
            QLabel#HomeSnapshotValue {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["stat_value"]}px;
                font-weight: {FONT_WEIGHTS["bold"]};
                border: none;
            }}
            QLabel#HomeSnapshotLabel {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
                border: none;
            }}
            """
        )

    def set_value(self, value: int) -> None:
        self.value_label.setText(str(value))


class HomePage(QWidget):
    """Compact operational landing page backed by ``HomeDashboardService``."""

    workspace_selected = Signal(str)

    def __init__(
        self,
        home_service: HomeDashboardService,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._service = home_service
        self._cards: list[WorkspaceCard] = []
        self._state_widget: Optional[QWidget] = None
        self._setup_ui()
        self.refresh()

    def _setup_ui(self) -> None:
        self.setObjectName("HomeDashboardV2")
        self.setStyleSheet(
            f"QWidget#HomeDashboardV2 {{ background-color: {COLORS['surface_app']}; }}"
        )

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.scroll_area = QScrollArea(self)
        self.scroll_area.setObjectName("HomeDashboardScrollArea")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setStyleSheet(
            f"QScrollArea#HomeDashboardScrollArea {{ background-color: {COLORS['surface_app']}; border: none; }}"
        )
        root.addWidget(self.scroll_area)

        self.container = QWidget(self.scroll_area)
        self.container.setObjectName("HomeDashboardContent")
        self.container.setStyleSheet(
            f"QWidget#HomeDashboardContent {{ background-color: {COLORS['surface_app']}; }}"
        )
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(
            SPACING["xxl"], SPACING["xl"], SPACING["xxl"], SPACING["xxl"]
        )
        self.container_layout.setSpacing(SPACING["xl"])
        self.scroll_area.setWidget(self.container)

        self._build_header()
        self._build_dashboard_content()

        self.state_host = QWidget(self.container)
        self.state_host.setObjectName("HomeDashboardStateHost")
        self.state_layout = QVBoxLayout(self.state_host)
        self.state_layout.setContentsMargins(0, SPACING["xl"], 0, 0)
        self.state_layout.setSpacing(0)
        self.state_host.setVisible(False)
        self.container_layout.addWidget(self.state_host, 1)
        self.container_layout.addStretch()

    def _build_header(self) -> None:
        header_layout = QHBoxLayout()
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(SPACING["lg"])

        copy_layout = QVBoxLayout()
        copy_layout.setContentsMargins(0, 0, 0, 0)
        copy_layout.setSpacing(SPACING["xs"])

        eyebrow = QLabel("OPERATIONS", self.container)
        eyebrow.setObjectName("HomeEyebrow")
        title = QLabel("Center overview", self.container)
        title.setObjectName("HomeTitle")
        subtitle = QLabel(
            "Workspace health and quick access to the areas available to you.",
            self.container,
        )
        subtitle.setObjectName("HomeSubtitle")
        subtitle.setWordWrap(True)

        copy_layout.addWidget(eyebrow)
        copy_layout.addWidget(title)
        copy_layout.addWidget(subtitle)
        header_layout.addLayout(copy_layout, 1)

        self.refresh_button = Button(
            "Refresh",
            variant=ButtonVariant.SECONDARY,
            size=ComponentSize.SMALL,
            parent=self.container,
        )
        self.refresh_button.setToolTip("Refresh dashboard data")
        self.refresh_button.clicked.connect(self._on_refresh_clicked)
        header_layout.addWidget(
            self.refresh_button,
            alignment=Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight,
        )

        header = QWidget(self.container)
        header.setObjectName("HomeDashboardHeader")
        header.setLayout(header_layout)
        header.setStyleSheet(
            f"""
            QLabel#HomeEyebrow {{
                color: {COLORS["action_accent"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["badge"]}px;
                font-weight: {FONT_WEIGHTS["bold"]};
            }}
            QLabel#HomeTitle {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["page_title"]}px;
                font-weight: {FONT_WEIGHTS["bold"]};
            }}
            QLabel#HomeSubtitle {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
            }}
            """
        )
        self.container_layout.addWidget(header)

    def _build_dashboard_content(self) -> None:
        self.dashboard_content = QWidget(self.container)
        self.dashboard_content.setObjectName("HomeOperationalContent")
        content_layout = QVBoxLayout(self.dashboard_content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(SPACING["xl"])

        overview_label = QLabel("Operational snapshot", self.dashboard_content)
        overview_label.setObjectName("HomeSectionTitle")
        content_layout.addWidget(overview_label)

        snapshot_layout = QHBoxLayout()
        snapshot_layout.setContentsMargins(0, 0, 0, 0)
        snapshot_layout.setSpacing(SPACING["md"])
        self.available_tile = _SnapshotTile("Available workspaces", "0", self.dashboard_content)
        self.healthy_tile = _SnapshotTile("Healthy", "0", self.dashboard_content)
        self.attention_tile = _SnapshotTile("Needs attention", "0", self.dashboard_content)
        snapshot_layout.addWidget(self.available_tile, 1)
        snapshot_layout.addWidget(self.healthy_tile, 1)
        snapshot_layout.addWidget(self.attention_tile, 1)
        content_layout.addLayout(snapshot_layout)

        self.attention_panel = QFrame(self.dashboard_content)
        self.attention_panel.setObjectName("HomeAttentionPanel")
        attention_layout = QHBoxLayout(self.attention_panel)
        attention_layout.setContentsMargins(
            SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"]
        )
        attention_layout.setSpacing(SPACING["md"])
        attention_title = QLabel("Attention", self.attention_panel)
        attention_title.setObjectName("HomeAttentionTitle")
        self.attention_details = QLabel("", self.attention_panel)
        self.attention_details.setObjectName("HomeAttentionDetails")
        self.attention_details.setWordWrap(True)
        attention_layout.addWidget(attention_title)
        attention_layout.addWidget(self.attention_details, 1)
        self.attention_panel.setStyleSheet(
            f"""
            QFrame#HomeAttentionPanel {{
                background-color: {COLORS["state_warning_bg"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["state_warning"]};
                border-radius: {RADIUS["md"]}px;
            }}
            QLabel#HomeAttentionTitle {{
                color: {COLORS["state_warning"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
            }}
            QLabel#HomeAttentionDetails {{
                color: {COLORS["text_secondary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
            }}
            """
        )
        self.attention_panel.setVisible(False)
        content_layout.addWidget(self.attention_panel)

        workspace_header = QVBoxLayout()
        workspace_header.setContentsMargins(0, 0, 0, 0)
        workspace_header.setSpacing(SPACING["xs"])
        workspace_title = QLabel("Workspaces", self.dashboard_content)
        workspace_title.setObjectName("HomeSectionTitle")
        workspace_help = QLabel(
            "Open an area to continue operational work.",
            self.dashboard_content,
        )
        workspace_help.setObjectName("HomeSectionHelp")
        workspace_header.addWidget(workspace_title)
        workspace_header.addWidget(workspace_help)
        content_layout.addLayout(workspace_header)

        self.workspace_grid = QGridLayout()
        self.workspace_grid.setContentsMargins(0, 0, 0, 0)
        self.workspace_grid.setHorizontalSpacing(SPACING["md"])
        self.workspace_grid.setVerticalSpacing(SPACING["md"])
        for column in range(3):
            self.workspace_grid.setColumnStretch(column, 1)
        content_layout.addLayout(self.workspace_grid)

        self.dashboard_content.setStyleSheet(
            f"""
            QLabel#HomeSectionTitle {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["section_title"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
            }}
            QLabel#HomeSectionHelp {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
            }}
            """
        )
        self.container_layout.addWidget(self.dashboard_content)

    def _on_refresh_clicked(self) -> None:
        self.refresh(force=True)

    def refresh(self, *, force: bool = False) -> None:
        """Refresh the Home projection; manual refresh also invalidates service cache."""
        try:
            if force and hasattr(self._service, "refresh"):
                self._service.refresh()
            self._populate_workspace_cards()
        except Exception:
            logger.exception("Failed to refresh Home Dashboard V2")
            self._show_error_state()

    def _populate_workspace_cards(self) -> None:
        """Compatibility method retained while rendering Dashboard V2."""
        summaries = list(self._service.get_workspace_summaries())
        if not summaries:
            self._clear_workspace_grid()
            self._show_empty_state()
            return

        self._render_summaries(summaries)
        self._show_dashboard_content()

    def _render_summaries(self, summaries: Iterable[WorkspaceSummary]) -> None:
        summaries = list(summaries)
        self._clear_workspace_grid()

        healthy = sum(1 for summary in summaries if summary.health_status == "good")
        attention = sum(
            1 for summary in summaries if summary.health_status in {"warning", "critical"}
        )
        self.available_tile.set_value(len(summaries))
        self.healthy_tile.set_value(healthy)
        self.attention_tile.set_value(attention)

        attention_messages = []
        for summary in summaries:
            if summary.health_status in {"warning", "critical"}:
                detail = summary.health_details.strip() or "Review this workspace"
                attention_messages.append(f"{summary.name}: {detail}")
        self.attention_details.setText("  |  ".join(attention_messages))
        self.attention_panel.setVisible(bool(attention_messages))

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
        self._state_widget = EmptyState(
            icon=None,
            title="No workspaces available",
            description="No operational areas are available for the current account.",
            parent=self.state_host,
        )
        self.state_layout.addWidget(self._state_widget)
        self.state_host.setVisible(True)

    def _show_error_state(self) -> None:
        self.dashboard_content.setVisible(False)
        self._clear_state()
        self._state_widget = ErrorState(
            title="Dashboard unavailable",
            description="Center overview could not be loaded. Try refreshing the data.",
            retry_text="Try again",
            retry_callback=self._on_refresh_clicked,
            parent=self.state_host,
        )
        self.state_layout.addWidget(self._state_widget)
        self.state_host.setVisible(True)

    def _on_workspace_clicked(self, workspace_id: str) -> None:
        self.workspace_selected.emit(workspace_id)
