# -*- coding: utf-8 -*-
"""Compact workspace access card for Home Dashboard V2."""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from centermanager.ui.design_system.foundation import (
    Badge,
    BadgeTone,
    Button,
    ButtonVariant,
    ComponentSize,
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


class WorkspaceCard(QFrame):
    """Text-first workspace summary with semantic health and quick action."""

    clicked = Signal(str)

    def __init__(
        self,
        workspace_id: str,
        name: str,
        icon: str,
        description: str,
        summary_text: str,
        health_status: str,
        health_details: str,
        quick_action_label: str = "Open",
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._workspace_id = workspace_id
        # Retained for constructor/API compatibility. Home V2 intentionally does
        # not render emoji or mixed icon languages.
        self._icon = icon
        self._health_status = health_status
        self._setup_ui(
            name,
            description,
            summary_text,
            health_status,
            health_details,
            quick_action_label,
        )

    @property
    def workspace_id(self) -> str:
        return self._workspace_id

    def _setup_ui(
        self,
        name: str,
        description: str,
        summary_text: str,
        health_status: str,
        health_details: str,
        quick_action_label: str,
    ) -> None:
        self.setObjectName("HomeWorkspaceCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumHeight(184)
        self.setAccessibleName(name)
        self.setToolTip(f"Open {name}")

        root = QVBoxLayout(self)
        root.setContentsMargins(
            SPACING["lg"], SPACING["lg"], SPACING["lg"], SPACING["lg"]
        )
        root.setSpacing(SPACING["sm"])

        heading = QHBoxLayout()
        heading.setContentsMargins(0, 0, 0, 0)
        heading.setSpacing(SPACING["sm"])

        self.name_label = QLabel(name, self)
        self.name_label.setObjectName("HomeWorkspaceName")
        self.name_label.setWordWrap(True)
        heading.addWidget(self.name_label, 1)

        status_text, tone = self._health_presentation(health_status)
        self.health_badge = Badge(status_text, tone=tone, parent=self)
        heading.addWidget(self.health_badge, alignment=Qt.AlignmentFlag.AlignTop)
        root.addLayout(heading)

        self.description_label = QLabel(description, self)
        self.description_label.setObjectName("HomeWorkspaceDescription")
        self.description_label.setWordWrap(True)
        root.addWidget(self.description_label)

        self.summary_label = QLabel(summary_text, self)
        self.summary_label.setObjectName("HomeWorkspaceSummary")
        self.summary_label.setWordWrap(True)
        root.addWidget(self.summary_label)

        self.health_details_label = QLabel(health_details, self)
        self.health_details_label.setObjectName("HomeWorkspaceHealthDetails")
        self.health_details_label.setWordWrap(True)
        self.health_details_label.setVisible(bool(health_details.strip()))
        root.addWidget(self.health_details_label)

        root.addStretch()

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.addStretch()
        action_text = quick_action_label.strip() or "Open"
        self.action_btn = Button(
            action_text,
            variant=ButtonVariant.GHOST,
            size=ComponentSize.SMALL,
            parent=self,
        )
        self.action_btn.setAccessibleName(f"Open {name}")
        self.action_btn.clicked.connect(self._emit_clicked)
        action_row.addWidget(self.action_btn)
        root.addLayout(action_row)

        self.setStyleSheet(
            f"""
            QFrame#HomeWorkspaceCard {{
                background-color: {COLORS["surface_card"]};
                border: {COMPONENT_METRICS["border_width"]}px solid {COLORS["border_default"]};
                border-radius: {RADIUS["lg"]}px;
            }}
            QFrame#HomeWorkspaceCard:hover {{
                background-color: {COLORS["surface_hover"]};
                border-color: {COLORS["border_strong"]};
            }}
            QLabel#HomeWorkspaceName {{
                color: {COLORS["text_primary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["card_title"]}px;
                font-weight: {FONT_WEIGHTS["semibold"]};
                border: none;
            }}
            QLabel#HomeWorkspaceDescription {{
                color: {COLORS["text_muted"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body_small"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
                border: none;
            }}
            QLabel#HomeWorkspaceSummary {{
                color: {COLORS["text_secondary"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["body"]}px;
                font-weight: {FONT_WEIGHTS["medium"]};
                border: none;
            }}
            QLabel#HomeWorkspaceHealthDetails {{
                color: {COLORS["state_warning"]};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY["caption"]}px;
                font-weight: {FONT_WEIGHTS["regular"]};
                border: none;
            }}
            """
        )

    @staticmethod
    def _health_presentation(health_status: str) -> tuple[str, BadgeTone]:
        normalized = (health_status or "").strip().lower()
        if normalized == "good":
            return "Healthy", BadgeTone.SUCCESS
        if normalized == "warning":
            return "Attention", BadgeTone.WARNING
        if normalized == "critical":
            return "Critical", BadgeTone.DANGER
        return "Status", BadgeTone.NEUTRAL

    def _emit_clicked(self) -> None:
        self.clicked.emit(self._workspace_id)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._emit_clicked()
        super().mousePressEvent(event)
