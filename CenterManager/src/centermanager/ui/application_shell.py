# -*- coding: utf-8 -*-
"""Application shell primitives for CenterManager.

PR-C keeps routine collaboration/editing state inside the fixed application
header. The feedback host remains reserved for exceptional/success feedback and
no longer grows a second row merely because Start/Finish Editing is running.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt, Signal
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsOpacityEffect, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from centermanager.core.application_identity import APPLICATION_DISPLAY_NAME, APPLICATION_PRODUCT_NAME
from centermanager.ui.application_icon import build_application_icon
from centermanager.ui.design_system.desktop import ElidedLabel, install_desktop_polish
from centermanager.ui.design_system.feedback import FeedbackController, FeedbackHost, FeedbackRequest
from centermanager.ui.design_system.foundation import Badge, Button
from centermanager.ui.design_system.tokens import COLORS, COMPONENT_METRICS, FONT_FAMILY, FONT_WEIGHTS, SPACING, TYPOGRAPHY


class Breadcrumbs(QWidget):
    """Compact shell breadcrumb with a navigable Home root."""
    home_clicked = Signal()

    def __init__(self, workspace_name: str, page_label: str, parent: Optional[QWidget] = None) -> None:
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
        self._workspace_label = ElidedLabel()
        self._page_label_widget = ElidedLabel()
        for label in (self._workspace_label, self._page_label_widget):
            label.setStyleSheet(f"color: {COLORS['text_muted']}; font-family: {FONT_FAMILY}; font-size: {TYPOGRAPHY['caption']}px; border: none;")
        self._separator_one = QLabel("›")
        self._separator_two = QLabel("›")
        for separator in (self._separator_one, self._separator_two):
            separator.setStyleSheet(f"color: {COLORS['gray_400']}; font-size: {TYPOGRAPHY['caption']}px; border: none;")
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
        self._page_label_widget.setStyleSheet(f"color: {COLORS['text_secondary']}; font-family: {FONT_FAMILY}; font-size: {TYPOGRAPHY['caption']}px; font-weight: {FONT_WEIGHTS['medium']}; border: none;")


class ApplicationTopBar(QFrame):
    """Balanced three-zone application header with inline WRITE-state UX."""
    start_edit_requested = Signal()
    finish_edit_requested = Signal()
    cancel_edit_requested = Signal()

    def __init__(self, *, user_name: str, role_name: str = "", runtime_version: str = "", sync_status: str = "disabled", feedback_controller: Optional[FeedbackController] = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("ApplicationTopBar")
        self.setMinimumHeight(COMPONENT_METRICS["app_top_bar_height"])
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self._editing_operation_id: Optional[str] = None
        shell_layout = QVBoxLayout(self)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self.header = QFrame(self)
        self.header.setObjectName("ApplicationTopBarHeader")
        self.header.setFixedHeight(COMPONENT_METRICS["app_top_bar_height"])
        layout = QHBoxLayout(self.header)
        layout.setContentsMargins(SPACING["lg"], 0, SPACING["lg"], 0)
        layout.setSpacing(SPACING["lg"])

        left_zone = QWidget(self.header)
        left_zone.setObjectName("ApplicationTopBarLeftZone")
        left_layout = QVBoxLayout(left_zone)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(1)
        brand_row = QHBoxLayout(); brand_row.setContentsMargins(0, 0, 0, 0); brand_row.setSpacing(SPACING["sm"])
        brand_label = QLabel("ANTECHKIDS")
        brand_label.setStyleSheet(f"color: {COLORS['action_primary']}; font-size: {TYPOGRAPHY['body_small']}px; font-weight: {FONT_WEIGHTS['bold']}; letter-spacing: 0.6px;")
        product_label = QLabel(APPLICATION_PRODUCT_NAME)
        product_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: {TYPOGRAPHY['body']}px; font-weight: {FONT_WEIGHTS['semibold']};")
        brand_row.addWidget(brand_label); brand_row.addWidget(product_label); brand_row.addStretch()
        meta_row = QHBoxLayout(); meta_row.setContentsMargins(0, 0, 0, 0); meta_row.setSpacing(SPACING["sm"])
        self.version_label = ElidedLabel(f"Runtime: {runtime_version}" if runtime_version else "Runtime")
        self.sync_label = ElidedLabel(f"Sync: {sync_status}")
        for label in (self.version_label, self.sync_label):
            label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: {TYPOGRAPHY['caption']}px;")
            meta_row.addWidget(label)
        meta_row.addStretch(); left_layout.addLayout(brand_row); left_layout.addLayout(meta_row)
        left_zone.setMinimumWidth(250)
        layout.addWidget(left_zone, 1)

        self.state_zone = QFrame(self.header)
        self.state_zone.setObjectName("ApplicationTopBarStateZone")
        state_layout = QHBoxLayout(self.state_zone)
        state_layout.setContentsMargins(SPACING["md"], SPACING["xs"], SPACING["md"], SPACING["xs"])
        state_layout.setSpacing(SPACING["sm"])
        self.mode_badge = Badge("Mode: READ", tone="neutral")
        self.editor_badge = Badge("No active editor", tone="neutral")
        self.mode_badge.setAccessibleName("Application editing mode")
        self.editor_badge.setAccessibleName("Active editor status")
        self.transaction_label = ElidedLabel("Ready")
        self.transaction_label.setStyleSheet(f"color: {COLORS['text_secondary']}; font-size: {TYPOGRAPHY['caption']}px; font-weight: {FONT_WEIGHTS['medium']};")
        self.start_edit_button = Button("Start editing", variant="primary", size="sm")
        self.finish_edit_button = Button("Finish editing", variant="accent", size="sm")
        self.cancel_edit_button = Button("Cancel request", variant="ghost", size="sm")
        self.start_edit_button.setAccessibleName("Start editing")
        self.finish_edit_button.setAccessibleName("Finish editing")
        self.cancel_edit_button.setAccessibleName("Cancel editing request")
        self.finish_edit_button.setVisible(False); self.cancel_edit_button.setVisible(False)
        self.start_edit_button.clicked.connect(self._request_start_editing)
        self.finish_edit_button.clicked.connect(self._request_finish_editing)
        self.cancel_edit_button.clicked.connect(self.cancel_edit_requested.emit)
        state_layout.addWidget(self.mode_badge); state_layout.addWidget(self.editor_badge); state_layout.addWidget(self.transaction_label, 1)
        state_layout.addWidget(self.start_edit_button); state_layout.addWidget(self.finish_edit_button); state_layout.addWidget(self.cancel_edit_button)
        layout.addWidget(self.state_zone, 2)
        self._state_opacity = QGraphicsOpacityEffect(self.state_zone)
        self.state_zone.setGraphicsEffect(self._state_opacity)
        self._state_animation = QPropertyAnimation(self._state_opacity, b"opacity", self)
        self._state_animation.setDuration(180)
        self._state_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        user_separator = QFrame(); user_separator.setFrameShape(QFrame.Shape.VLine); user_separator.setStyleSheet(f"color: {COLORS['border_default']};")
        layout.addWidget(user_separator)
        user_layout = QVBoxLayout(); user_layout.setContentsMargins(0, 0, 0, 0); user_layout.setSpacing(0)
        self.user_label = ElidedLabel(user_name)
        self.user_label.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: {TYPOGRAPHY['body_small']}px; font-weight: {FONT_WEIGHTS['semibold']};")
        self.role_label = ElidedLabel(role_name or "User")
        self.role_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: {TYPOGRAPHY['caption']}px;")
        user_layout.addWidget(self.user_label, alignment=Qt.AlignmentFlag.AlignRight); user_layout.addWidget(self.role_label, alignment=Qt.AlignmentFlag.AlignRight)
        layout.addLayout(user_layout)

        shell_layout.addWidget(self.header)
        self.feedback_controller = feedback_controller or FeedbackController(self)
        self.feedback_host = FeedbackHost(self.feedback_controller, parent=self)
        shell_layout.addWidget(self.feedback_host)
        self.setStyleSheet(f"""
            QFrame#ApplicationTopBar {{ background-color: {COLORS['surface_page']}; border: none; }}
            QFrame#ApplicationTopBarHeader {{ background-color: {COLORS['surface_page']}; border: none; border-bottom: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_default']}; }}
            QFrame#ApplicationTopBarHeader QLabel {{ border: none; background: transparent; font-family: {FONT_FAMILY}; }}
            QFrame#ApplicationTopBarStateZone {{ background-color: {COLORS['surface_hover']}; border: {COMPONENT_METRICS['border_width']}px solid {COLORS['border_subtle']}; border-radius: {SPACING['sm']}px; }}
        """)
        self.mode_label = self.mode_badge; self.waiting_indicator = self.editor_badge; self.tx_state_label = self.transaction_label
        self.start_edit_btn = self.start_edit_button; self.finish_edit_btn = self.finish_edit_button; self.cancel_btn = self.cancel_edit_button
        self.resize(self.width(), COMPONENT_METRICS["app_top_bar_height"])
        top_level = self.window()
        if top_level is not self:
            top_level.setWindowTitle(APPLICATION_DISPLAY_NAME); top_level.setWindowIcon(build_application_icon())
        install_desktop_polish(self.window())

    def _animate_state_change(self) -> None:
        self._state_animation.stop(); self._state_animation.setStartValue(0.58); self._state_animation.setEndValue(1.0); self._state_animation.start()

    def _request_start_editing(self) -> None:
        self._run_edit_operation("start-editing", "Starting editing…", self.start_edit_requested)

    def _request_finish_editing(self) -> None:
        self._run_edit_operation("finish-editing", "Finishing & syncing…", self.finish_edit_requested)

    def _run_edit_operation(self, operation_id: str, message: str, signal) -> bool:
        """Project routine busy state inline; FeedbackHost is not used here."""
        if self._editing_operation_id is not None: return False
        self._editing_operation_id = operation_id
        self.set_transaction_text(message)
        animate = getattr(self, "_animate_state_change", None)
        if callable(animate): animate()
        for button in (self.start_edit_button, self.finish_edit_button, self.cancel_edit_button): button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor); QApplication.processEvents()
        try:
            signal.emit(); return True
        finally:
            QApplication.restoreOverrideCursor(); self._editing_operation_id = None
            waiting = self.start_edit_button.text().strip().lower().startswith("waiting")
            self.start_edit_button.setEnabled(not waiting); self.finish_edit_button.setEnabled(True); self.cancel_edit_button.setEnabled(True)
            if callable(animate): animate()

    def set_mode(self, mode: str, tone: str = "neutral") -> None:
        changed = self.mode_badge.text() != f"Mode: {mode}"; self.mode_badge.setText(f"Mode: {mode}"); self.mode_badge.set_tone(tone)
        if changed: self._animate_state_change()

    def set_editor_state(self, text: str, tone: str = "neutral") -> None:
        changed = self.editor_badge.text() != text; self.editor_badge.setText(text); self.editor_badge.set_tone(tone)
        if changed: self._animate_state_change()

    def set_transaction_text(self, text: str) -> None: self.transaction_label.setText(text)
    def set_runtime_version(self, version: str) -> None: self.version_label.setText(f"Runtime: v{version}" if not version.startswith("v") else f"Runtime: {version}")
    def set_sync_status(self, status: str) -> None: self.sync_label.setText(f"Sync: {status}")

    # ---- UI-PROD-07 feedback API ----
    def show_feedback(self, request: FeedbackRequest) -> FeedbackRequest: return self.feedback_controller.publish(request)
    def notify_info(self, message: str, **kwargs) -> FeedbackRequest: return self.feedback_controller.info(message, **kwargs)
    def notify_success(self, message: str, **kwargs) -> FeedbackRequest: return self.feedback_controller.success(message, **kwargs)
    def notify_warning(self, message: str, **kwargs) -> FeedbackRequest: return self.feedback_controller.warning(message, **kwargs)
    def notify_error(self, message: str, **kwargs) -> FeedbackRequest: return self.feedback_controller.error(message, **kwargs)
    def begin_operation(self, operation_id: str, message: str = "Working…") -> bool: return self.feedback_controller.begin_operation(operation_id, message)
    def finish_operation(self, operation_id: str) -> bool: return self.feedback_controller.finish_operation(operation_id)


__all__ = ["ApplicationTopBar", "Breadcrumbs"]