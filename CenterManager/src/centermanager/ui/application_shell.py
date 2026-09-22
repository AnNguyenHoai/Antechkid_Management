# -*- coding: utf-8 -*-
"""Application shell primitives for CenterManager.

UI-PROD-03 keeps application-wide state in one top bar and page-local context
inside workspace headers. UI-PROD-07 adds the canonical application feedback
region while preserving the existing shell/transaction compatibility aliases.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from centermanager.ui.design_system.feedback import (
    FeedbackController,
    FeedbackHost,
    FeedbackRequest,
)
from centermanager.ui.design_system.foundation import Badge, Button
from centermanager.ui.design_system.tokens import (
    COLORS,
    COMPONENT_METRICS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    SPACING,
    TYPOGRAPHY,
)


class Breadcrumbs(QWidget):
    """Compact shell breadcrumb with a navigable Home root."""

    home_clicked = Signal()

    def __init__(
        self,
        workspace_name: str,
        page_label: str,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._workspace_name = workspace_name
        self._page_label = page_label

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(SPACING["xs"])

        self.home_button = Button("Home", variant="ghost", size="sm")
        self.home_button.setAccessibleName("Back to home")
        self.home_button.clicked.connect(self.home_clicked.emit)
        self._layout.addWidget(self.home_button)

        self._workspace_label = QLabel()
        self._page_label_widget = QLabel()
        for label in (self._workspace_label, self._page_label_widget):
            label.setStyleSheet(
                f"color: {COLORS['text_muted']}; font-family: {FONT_FAMILY}; "
                f"font-size: {TYPOGRAPHY['caption']}px; border: none;"
            )

        self._separator_one = QLabel("›")
        self._separator_two = QLabel("›")
        for separator in (self._separator_one, self._separator_two):
            separator.setStyleSheet(
                f"color: {COLORS['gray_400']}; font-size: {TYPOGRAPHY['caption']}px; border: none;"
            )

        self._layout.addWidget(self._separator_one)
        self._layout.addWidget(self._workspace_label)
        self._layout.addWidget(self._separator_two)
        self._layout.addWidget(self._page_label_widget)
        self._layout.addStretch()
        self.set_path(workspace_name, page_label)

    def set_path(self, workspace_name: str, page_label: str) -> None:
        self._workspace_name = workspace_name
        self._page_label = page_label
        self._workspace_label.setText(workspace_name)
        self._page_label_widget.setText(page_label)
        self._page_label_widget.setStyleSheet(
            f"color: {COLORS['text_secondary']}; font-family: {FONT_FAMILY}; "
            f"font-size: {TYPOGRAPHY['caption']}px; font-weight: {FONT_WEIGHTS['medium']}; border: none;"
        )


class ApplicationTopBar(QFrame):
    """Application-wide product, runtime, user, write-state and feedback shell.

    The first row preserves the UI-PROD-03 top-bar contract. ``FeedbackHost``
    lives directly below that row and is hidden when idle, so existing layouts
    retain their 60px shell height until feedback or an operation is active.
    """

    start_edit_requested = Signal()
    finish_edit_requested = Signal()
    cancel_edit_requested = Signal()

    def __init__(
        self,
        *,
        user_name: str,
        role_name: str = "",
        runtime_version: str = "",
        sync_status: str = "disabled",
        feedback_controller: Optional[FeedbackController] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("ApplicationTopBar")
        self.setMinimumHeight(COMPONENT_METRICS["app_top_bar_height"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        shell_layout = QVBoxLayout(self)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)

        self.header = QFrame(self)
        self.header.setObjectName("ApplicationTopBarHeader")
        self.header.setFixedHeight(COMPONENT_METRICS["app_top_bar_height"])
        layout = QHBoxLayout(self.header)
        layout.setContentsMargins(SPACING["lg"], 0, SPACING["lg"], 0)
        layout.setSpacing(SPACING["md"])

        brand_layout = QVBoxLayout()
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(0)
        brand_label = QLabel("AN TECHKIDS")
        brand_label.setStyleSheet(
            f"color: {COLORS['action_primary']}; font-size: {TYPOGRAPHY['body_small']}px; "
            f"font-weight: {FONT_WEIGHTS['bold']}; letter-spacing: 0.6px;"
        )
        product_label = QLabel("Center Manager")
        product_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: {TYPOGRAPHY['body']}px; "
            f"font-weight: {FONT_WEIGHTS['semibold']};"
        )
        brand_layout.addWidget(brand_label)
        brand_layout.addWidget(product_label)
        layout.addLayout(brand_layout)

        meta_separator = QFrame()
        meta_separator.setFrameShape(QFrame.Shape.VLine)
        meta_separator.setStyleSheet(f"color: {COLORS['border_default']};")
        layout.addWidget(meta_separator)

        self.version_label = QLabel(f"Runtime: {runtime_version}" if runtime_version else "Runtime")
        self.sync_label = QLabel(f"Sync: {sync_status}")
        for label in (self.version_label, self.sync_label):
            label.setStyleSheet(
                f"color: {COLORS['text_muted']}; font-size: {TYPOGRAPHY['caption']}px;"
            )
            layout.addWidget(label)

        layout.addStretch()

        self.mode_badge = Badge("Mode: READ", tone="neutral")
        self.editor_badge = Badge("No active editor", tone="neutral")
        layout.addWidget(self.mode_badge)
        layout.addWidget(self.editor_badge)

        self.transaction_label = QLabel("Ready")
        self.transaction_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: {TYPOGRAPHY['caption']}px;"
        )
        layout.addWidget(self.transaction_label)

        self.start_edit_button = Button("Start editing", variant="primary", size="sm")
        self.finish_edit_button = Button("Finish editing", variant="accent", size="sm")
        self.cancel_edit_button = Button("Cancel request", variant="ghost", size="sm")
        self.finish_edit_button.setVisible(False)
        self.cancel_edit_button.setVisible(False)
        self.start_edit_button.clicked.connect(self.start_edit_requested.emit)
        self.finish_edit_button.clicked.connect(self.finish_edit_requested.emit)
        self.cancel_edit_button.clicked.connect(self.cancel_edit_requested.emit)
        layout.addWidget(self.start_edit_button)
        layout.addWidget(self.finish_edit_button)
        layout.addWidget(self.cancel_edit_button)

        user_separator = QFrame()
        user_separator.setFrameShape(QFrame.Shape.VLine)
        user_separator.setStyleSheet(f"color: {COLORS['border_default']};")
        layout.addWidget(user_separator)

        user_layout = QVBoxLayout()
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(0)
        self.user_label = QLabel(user_name)
        self.user_label.setStyleSheet(
            f"color: {COLORS['text_primary']}; font-size: {TYPOGRAPHY['body_small']}px; "
            f"font-weight: {FONT_WEIGHTS['semibold']};"
        )
        self.role_label = QLabel(role_name or "User")
        self.role_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; font-size: {TYPOGRAPHY['caption']}px;"
        )
        user_layout.addWidget(self.user_label, alignment=Qt.AlignmentFlag.AlignRight)
        user_layout.addWidget(self.role_label, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(user_layout)

        shell_layout.addWidget(self.header)

        # UI-PROD-07: one application-level feedback path. Page empty/loading/
        # error states remain owned by StateView in the page content area.
        self.feedback_controller = feedback_controller or FeedbackController(self)
        self.feedback_host = FeedbackHost(self.feedback_controller, parent=self)
        shell_layout.addWidget(self.feedback_host)

        self.setStyleSheet(
            f"""
            QFrame#ApplicationTopBar {{
                background-color: {COLORS['surface_page']};
                border: none;
            }}
            QFrame#ApplicationTopBarHeader {{
                background-color: {COLORS['surface_page']};
                border: none;
                border-bottom: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_default']};
            }}
            QFrame#ApplicationTopBarHeader QLabel {{
                border: none;
                background: transparent;
                font-family: {FONT_FAMILY};
            }}
            """
        )

        # Compatibility aliases used by MainWindow's existing transaction code.
        self.mode_label = self.mode_badge
        self.waiting_indicator = self.editor_badge
        self.tx_state_label = self.transaction_label
        self.start_edit_btn = self.start_edit_button
        self.finish_edit_btn = self.finish_edit_button
        self.cancel_btn = self.cancel_edit_button

    def set_mode(self, mode: str, tone: str = "neutral") -> None:
        self.mode_badge.setText(f"Mode: {mode}")
        self.mode_badge.set_tone(tone)

    def set_editor_state(self, text: str, tone: str = "neutral") -> None:
        self.editor_badge.setText(text)
        self.editor_badge.set_tone(tone)

    def set_transaction_text(self, text: str) -> None:
        self.transaction_label.setText(text)

    def set_runtime_version(self, version: str) -> None:
        self.version_label.setText(
            f"Runtime: v{version}" if not version.startswith("v") else f"Runtime: {version}"
        )

    def set_sync_status(self, status: str) -> None:
        self.sync_label.setText(f"Sync: {status}")

    # ---- UI-PROD-07 shell feedback API ---------------------------------
    def show_feedback(self, request: FeedbackRequest) -> FeedbackRequest:
        return self.feedback_controller.publish(request)

    def notify_info(self, message: str, **kwargs) -> FeedbackRequest:
        return self.feedback_controller.info(message, **kwargs)

    def notify_success(self, message: str, **kwargs) -> FeedbackRequest:
        return self.feedback_controller.success(message, **kwargs)

    def notify_warning(self, message: str, **kwargs) -> FeedbackRequest:
        return self.feedback_controller.warning(message, **kwargs)

    def notify_error(self, message: str, **kwargs) -> FeedbackRequest:
        return self.feedback_controller.error(message, **kwargs)

    def begin_operation(self, operation_id: str, message: str = "Working…") -> bool:
        return self.feedback_controller.begin_operation(operation_id, message)

    def finish_operation(self, operation_id: str) -> bool:
        return self.feedback_controller.finish_operation(operation_id)


__all__ = ["ApplicationTopBar", "Breadcrumbs"]
