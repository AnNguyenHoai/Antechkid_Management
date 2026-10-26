# -*- coding: utf-8 -*-
"""Application shell primitives for CenterManager.

PR-E keeps routine collaboration/editing progress inside the fixed application
header. Start/Finish Editing receive a lightweight animated activity indicator
and truthful transition copy; the feedback host remains reserved for exceptional
or durable success/warning/error feedback.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QTimer, Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect, QHBoxLayout, QLabel, QSizePolicy, QVBoxLayout, QWidget

from centermanager.core.application_identity import APPLICATION_DISPLAY_NAME, APPLICATION_PRODUCT_NAME
from centermanager.ui.application_icon import build_application_icon
from centermanager.ui.design_system.desktop import ElidedLabel, install_desktop_polish
from centermanager.ui.design_system.feedback import FeedbackController, FeedbackHost, FeedbackRequest
from centermanager.ui.app_icon import AppIcon
from centermanager.ui.design_system.foundation import Button
from centermanager.ui.design_system.tokens import COLORS, COMPONENT_METRICS, FONT_FAMILY, FONT_WEIGHTS, RADIUS, SPACING, TYPOGRAPHY


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


class _HeaderPill(QFrame):
    """Compact icon + text status pill used by the application header."""

    _PALETTES = {
        "neutral": (COLORS["gray_50"], COLORS["text_secondary"], COLORS["border_default"]),
        "info": (COLORS["blue_50"], COLORS["brand_blue_900"], COLORS["blue_100"]),
        "success": (COLORS["state_success_bg"], COLORS["state_success"], COLORS["green_50"]),
        "warning": (COLORS["state_warning_bg"], COLORS["state_warning"], COLORS["amber_50"]),
        "danger": (COLORS["state_danger_bg"], COLORS["state_danger"], COLORS["red_100"]),
    }

    def __init__(
        self,
        text: str,
        *,
        icon: str,
        tone: str = "neutral",
        compact: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("HeaderStatusPill")
        self._tone = tone if tone in self._PALETTES else "neutral"
        self._compact = compact

        layout = QHBoxLayout(self)
        layout.setContentsMargins(
            SPACING["sm"] if compact else SPACING["md"],
            0,
            SPACING["sm"] if compact else SPACING["md"],
            0,
        )
        layout.setSpacing(SPACING["xs"])

        self.icon = AppIcon(icon, size=14, tile_size=16, parent=self)
        layout.addWidget(self.icon)
        self.label = QLabel(self._clean_text(text), self)
        self.label.setObjectName("HeaderStatusPillText")
        layout.addWidget(self.label)

        self.setFixedHeight(30 if compact else 34)
        self._apply_tone()

    @staticmethod
    def _clean_text(text: str) -> str:
        value = (text or "").strip()
        for prefix in ("✏️ ", "🔒 ", "● ", "✓ ", "⚠️ "):
            if value.startswith(prefix):
                value = value[len(prefix):]
        return value

    def text(self) -> str:
        return self.label.text()

    def setText(self, text: str) -> None:
        self.label.setText(self._clean_text(text))

    def set_tone(self, tone: str) -> None:
        self._tone = tone if tone in self._PALETTES else "neutral"
        self._apply_tone()

    def _apply_tone(self) -> None:
        bg, fg, border = self._PALETTES[self._tone]
        self.icon.set_color(fg)
        self.setStyleSheet(
            f"""
            QFrame#HeaderStatusPill {{
                background: {bg};
                border: 1px solid {border};
                border-radius: {RADIUS['md']}px;
            }}
            QLabel#HeaderStatusPillText {{
                background: transparent;
                border: none;
                color: {fg};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['medium']};
            }}
            """
        )


class _EditingGuidancePanel(QFrame):
    """State-driven guidance that explains the next editing action."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setObjectName("EditingGuidancePanel")
        self.setMinimumHeight(72)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(SPACING["lg"], SPACING["md"], SPACING["lg"], SPACING["md"])
        layout.setSpacing(SPACING["md"])

        self.icon = AppIcon(
            "info",
            size=20,
            color=COLORS["action_primary"],
            tile_color=COLORS["blue_50"],
            tile_size=36,
            parent=self,
        )
        layout.addWidget(self.icon)

        self.label = QLabel(self)
        self.label.setObjectName("EditingGuidanceText")
        self.label.setWordWrap(True)
        layout.addWidget(self.label, 1)

        self.setStyleSheet(
            f"""
            QFrame#EditingGuidancePanel {{
                background: {COLORS['blue_50']};
                border: 1px solid {COLORS['blue_100']};
                border-radius: {RADIUS['lg']}px;
            }}
            QLabel#EditingGuidanceText {{
                background: transparent;
                border: none;
                color: {COLORS['text_secondary']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body']}px;
                font-weight: {FONT_WEIGHTS['regular']};
            }}
            """
        )

    def set_message(self, message: str) -> None:
        self.label.setText(message)


class ApplicationTopBar(QFrame):
    """Three-zone application header: brand, guidance, and editing/session controls."""
    start_edit_requested = Signal()
    finish_edit_requested = Signal()
    cancel_edit_requested = Signal()

    _ACTIVITY_FRAMES = ("◐", "◓", "◑", "◒")

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
        self._editing_operation_id: Optional[str] = None
        self._activity_frame_index = 0
        self._activity_message = ""
        self._mode = "READ"
        self._editor_text = "No active editor"
        self._transaction_text = "Ready"

        self._activity_timer = QTimer(self)
        self._activity_timer.setInterval(140)
        self._activity_timer.timeout.connect(self._advance_activity_frame)

        shell_layout = QVBoxLayout(self)
        shell_layout.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], 0)
        shell_layout.setSpacing(0)

        self.header = QFrame(self)
        self.header.setObjectName("ApplicationHeroHeader")
        self.header.setMinimumHeight(COMPONENT_METRICS["hero_header_card_height"])
        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(SPACING["xl"], SPACING["lg"], SPACING["xl"], SPACING["lg"])
        header_layout.setSpacing(SPACING["xl"])

        # Zone 1: brand + runtime/sync metadata.
        brand_zone = QWidget(self.header)
        brand_zone.setObjectName("HeaderBrandZone")
        brand_layout = QVBoxLayout(brand_zone)
        brand_layout.setContentsMargins(0, 0, 0, 0)
        brand_layout.setSpacing(SPACING["md"])

        brand_row = QHBoxLayout()
        brand_row.setContentsMargins(0, 0, 0, 0)
        brand_row.setSpacing(SPACING["md"])
        brand_label = QLabel("ANTECHKIDS", brand_zone)
        brand_label.setObjectName("HeroBrand")
        divider = QFrame(brand_zone)
        divider.setObjectName("HeroBrandDivider")
        divider.setFixedSize(1, 28)
        self.product_label = QLabel(APPLICATION_PRODUCT_NAME, brand_zone)
        self.product_label.setObjectName("HeroProduct")
        brand_row.addWidget(brand_label)
        brand_row.addWidget(divider)
        brand_row.addWidget(self.product_label)
        brand_row.addStretch()

        meta_row = QHBoxLayout()
        meta_row.setContentsMargins(0, 0, 0, 0)
        meta_row.setSpacing(SPACING["sm"])
        self.version_label = _HeaderPill(
            f"Runtime: {runtime_version}" if runtime_version else "Runtime",
            icon="warning",
            tone="neutral",
            compact=True,
            parent=brand_zone,
        )
        self.sync_label = _HeaderPill(
            f"Sync: {sync_status}",
            icon="check",
            tone="info",
            compact=True,
            parent=brand_zone,
        )
        meta_row.addWidget(self.version_label)
        meta_row.addWidget(self.sync_label)
        meta_row.addStretch()
        brand_layout.addLayout(brand_row)
        brand_layout.addLayout(meta_row)
        header_layout.addWidget(brand_zone, 32)

        # Zone 2: contextual editing guidance.
        self.guidance_panel = _EditingGuidancePanel(self.header)
        self.guidance_panel.setMinimumWidth(280)
        header_layout.addWidget(self.guidance_panel, 36)

        # Zone 3: editing state + primary action + user identity.
        control_zone = QWidget(self.header)
        control_zone.setObjectName("HeaderControlZone")
        control_layout = QVBoxLayout(control_zone)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(SPACING["md"])

        status_row = QHBoxLayout()
        status_row.setContentsMargins(0, 0, 0, 0)
        status_row.setSpacing(SPACING["sm"])
        status_row.addStretch()

        self.mode_badge = _HeaderPill(
            "Mode: READ", icon="edit", tone="info", parent=control_zone
        )
        self.mode_badge.setAccessibleName("Application editing mode")
        self.editor_badge = _HeaderPill(
            "No active editor", icon="users", tone="info", parent=control_zone
        )
        self.editor_badge.setAccessibleName("Active editor status")
        self.transaction_label = _HeaderPill(
            "Ready", icon="check", tone="success", parent=control_zone
        )
        status_row.addWidget(self.mode_badge)
        status_row.addWidget(self.editor_badge)
        status_row.addWidget(self.transaction_label)

        self.activity_label = QLabel("", control_zone)
        self.activity_label.setObjectName("EditingActivityIndicator")
        self.activity_label.setFixedWidth(18)
        self.activity_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.activity_label.setVisible(False)
        self.activity_label.setAccessibleName("Editing operation in progress")
        status_row.addWidget(self.activity_label)
        control_layout.addLayout(status_row)

        action_row = QHBoxLayout()
        action_row.setContentsMargins(0, 0, 0, 0)
        action_row.setSpacing(SPACING["md"])
        action_row.addStretch()

        self.start_edit_button = Button("Start editing", variant="primary", size="lg")
        self.finish_edit_button = Button("Finish editing", variant="primary", size="lg")
        self.cancel_edit_button = Button("Cancel request", variant="ghost", size="sm")
        for button in (self.start_edit_button, self.finish_edit_button):
            button.setFixedHeight(COMPONENT_METRICS["hero_header_cta_height"])
            button.setMinimumWidth(168)
        self.start_edit_button.setObjectName("HeroPrimaryEditAction")
        self.finish_edit_button.setObjectName("HeroPrimaryEditAction")
        self.start_edit_button.setAccessibleName("Start editing")
        self.finish_edit_button.setAccessibleName("Finish editing")
        self.cancel_edit_button.setAccessibleName("Cancel editing request")
        self.finish_edit_button.setVisible(False)
        self.cancel_edit_button.setVisible(False)
        self.start_edit_button.clicked.connect(self._request_start_editing)
        self.finish_edit_button.clicked.connect(self._request_finish_editing)
        self.cancel_edit_button.clicked.connect(self.cancel_edit_requested.emit)
        action_row.addWidget(self.start_edit_button)
        action_row.addWidget(self.finish_edit_button)
        action_row.addWidget(self.cancel_edit_button)

        user_divider = QFrame(control_zone)
        user_divider.setObjectName("HeroUserDivider")
        user_divider.setFixedSize(1, 38)
        action_row.addWidget(user_divider)

        initials = "".join(part[:1] for part in (user_name or "U").split()[:2]).upper() or "U"
        self.user_avatar = QLabel(initials, control_zone)
        self.user_avatar.setObjectName("HeroUserAvatar")
        self.user_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.user_avatar.setFixedSize(44, 44)
        action_row.addWidget(self.user_avatar)

        user_layout = QVBoxLayout()
        user_layout.setContentsMargins(0, 0, 0, 0)
        user_layout.setSpacing(1)
        self.user_label = ElidedLabel(user_name)
        self.user_label.setObjectName("HeroUserName")
        self.role_label = ElidedLabel(role_name or "User")
        self.role_label.setObjectName("HeroUserRole")
        user_layout.addWidget(self.user_label)
        user_layout.addWidget(self.role_label)
        action_row.addLayout(user_layout)
        control_layout.addLayout(action_row)
        header_layout.addWidget(control_zone, 32)

        accent = QFrame(self.header)
        accent.setObjectName("HeroAccentLine")
        accent.setFixedHeight(COMPONENT_METRICS["hero_header_accent_height"])

        hero_stack = QVBoxLayout()
        hero_stack.setContentsMargins(0, 0, 0, 0)
        hero_stack.setSpacing(0)
        hero_stack.addWidget(self.header)
        hero_stack.addWidget(accent)
        hero_host = QWidget(self)
        hero_host.setLayout(hero_stack)
        shell_layout.addWidget(hero_host)

        self._header_shadow = QGraphicsDropShadowEffect(self.header)
        self._header_shadow.setBlurRadius(24)
        self._header_shadow.setOffset(0, 5)
        shadow_color = QColor(COLORS["shadow_color"])
        shadow_color.setAlpha(28)
        self._header_shadow.setColor(shadow_color)
        self.header.setGraphicsEffect(self._header_shadow)

        self.feedback_controller = feedback_controller or FeedbackController(self)
        self.feedback_host = FeedbackHost(self.feedback_controller, parent=self)
        shell_layout.addWidget(self.feedback_host)

        self.state_zone = control_zone
        self.brand_zone = brand_zone
        self.control_zone = control_zone
        self._state_animation = QPropertyAnimation(
            self._header_shadow, b"blurRadius", self
        )
        self._state_animation.setDuration(180)
        self._state_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        self.setStyleSheet(
            f"""
            QFrame#ApplicationTopBar {{
                background: transparent;
                border: none;
            }}
            QFrame#ApplicationHeroHeader {{
                background: {COLORS['surface_card']};
                border: 1px solid {COLORS['border_default']};
                border-top-left-radius: {RADIUS['xl']}px;
                border-top-right-radius: {RADIUS['xl']}px;
            }}
            QFrame#ApplicationHeroHeader QLabel {{
                border: none;
                background: transparent;
                font-family: {FONT_FAMILY};
            }}
            QLabel#HeroBrand {{
                color: {COLORS['brand_blue_900']};
                font-size: {TYPOGRAPHY['page_title']}px;
                font-weight: {FONT_WEIGHTS['bold']};
                letter-spacing: 0.8px;
            }}
            QFrame#HeroBrandDivider, QFrame#HeroUserDivider {{
                background: {COLORS['border_default']};
                border: none;
            }}
            QLabel#HeroProduct {{
                color: {COLORS['text_primary']};
                font-size: {TYPOGRAPHY['section_title']}px;
                font-weight: {FONT_WEIGHTS['medium']};
            }}
            QLabel#HeroUserAvatar {{
                color: {COLORS['brand_blue_900']};
                background: {COLORS['state_warning_bg']};
                border: none;
                border-radius: 22px;
                font-size: {TYPOGRAPHY['body_large']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            QLabel#HeroUserName {{
                color: {COLORS['text_primary']};
                font-size: {TYPOGRAPHY['body']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
            }}
            QLabel#HeroUserRole {{
                color: {COLORS['text_muted']};
                font-size: {TYPOGRAPHY['caption']}px;
            }}
            QFrame#HeroAccentLine {{
                background: {COLORS['action_accent']};
                border: none;
                border-bottom-left-radius: 4px;
                border-bottom-right-radius: 4px;
            }}
            QLabel#EditingActivityIndicator {{
                color: {COLORS['action_primary']};
                font-size: {TYPOGRAPHY['body']}px;
                font-weight: {FONT_WEIGHTS['bold']};
            }}
            QPushButton#HeroPrimaryEditAction {{
                border-radius: {RADIUS['md']}px;
                font-size: {TYPOGRAPHY['body_large']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
                padding: 0 {SPACING['xl']}px;
            }}
            """
        )

        # Backward-compatible aliases used by MainWindow and legacy observers.
        self.mode_label = self.mode_badge
        self.waiting_indicator = self.editor_badge
        self.tx_state_label = self.transaction_label
        self.start_edit_btn = self.start_edit_button
        self.finish_edit_btn = self.finish_edit_button
        self.cancel_btn = self.cancel_edit_button

        self._refresh_guidance()

        top_level = self.window()
        if top_level is not self:
            top_level.setWindowTitle(APPLICATION_DISPLAY_NAME)
            top_level.setWindowIcon(build_application_icon())
        install_desktop_polish(self.window())

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        width = self.width()
        compact = width < COMPONENT_METRICS["hero_header_compact_breakpoint"]
        narrow = width < COMPONENT_METRICS["hero_header_guidance_breakpoint"]

        self.product_label.setVisible(not compact)
        self.guidance_panel.setVisible(not narrow)
        if compact:
            self.start_edit_button.setMinimumWidth(144)
            self.finish_edit_button.setMinimumWidth(144)
        else:
            self.start_edit_button.setMinimumWidth(168)
            self.finish_edit_button.setMinimumWidth(168)

    def _animate_state_change(self) -> None:
        self._state_animation.stop()
        self._state_animation.setStartValue(18.0)
        self._state_animation.setEndValue(24.0)
        self._state_animation.start()

    def _refresh_guidance(self) -> None:
        mode = self._mode.upper()
        tx = self._transaction_text.lower()

        if "conflict" in mode or "changed on another" in tx:
            message = "Data changed elsewhere. Resolve or refresh before continuing."
        elif "recover" in tx or "recovery" in tx or "paused" in tx or "stale" in tx:
            message = "Editing is paused. Recover the edit session before changing more data."
        elif "finish" in tx or "saving" in tx or "publishing" in tx:
            message = "Saving and synchronizing your changes. Keep the application open."
        elif "waiting" in tx:
            message = "Another edit session is active. Your request will continue when editing becomes available."
        elif "failed" in tx or "offline" in tx:
            message = "Changes are not fully synchronized yet. Review the status before continuing."
        elif mode == "WRITE" or tx == "editing":
            message = "After changing data, click Finish editing so your changes are saved and synchronized."
        else:
            message = "Click Start editing when you need to change data. Read-only browsing remains available."
        self.guidance_panel.set_message(message)

    def _start_activity(self, message: str) -> None:
        """Show indeterminate activity without claiming backend progress percentage."""
        self._activity_message = message
        self._activity_frame_index = 0
        self.activity_label.setText(self._ACTIVITY_FRAMES[0])
        self.activity_label.setVisible(True)
        self.set_transaction_text(message)
        self._activity_timer.start()

    def _advance_activity_frame(self) -> None:
        if not self._activity_timer.isActive():
            return
        self._activity_frame_index = (self._activity_frame_index + 1) % len(self._ACTIVITY_FRAMES)
        self.activity_label.setText(self._ACTIVITY_FRAMES[self._activity_frame_index])

    def _stop_activity(self) -> None:
        self._activity_timer.stop()
        self.activity_label.clear()
        self.activity_label.setVisible(False)
        self._activity_message = ""

    def _request_start_editing(self) -> None:
        self._run_edit_operation("start-editing", "Preparing edit access…", self.start_edit_requested)

    def _request_finish_editing(self) -> None:
        self._run_edit_operation("finish-editing", "Saving and syncing changes…", self.finish_edit_requested)

    def _run_edit_operation(self, operation_id: str, message: str, signal) -> bool:
        """Project routine busy state inline; FeedbackHost is not used here."""
        if self._editing_operation_id is not None:
            return False
        self._editing_operation_id = operation_id
        self._start_activity(message)
        self._animate_state_change()
        for button in (self.start_edit_button, self.finish_edit_button, self.cancel_edit_button):
            button.setEnabled(False)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            signal.emit()
            return True
        finally:
            QApplication.restoreOverrideCursor()
            self._editing_operation_id = None
            self._stop_activity()
            waiting = self.start_edit_button.text().strip().lower().startswith("waiting")
            self.start_edit_button.setEnabled(not waiting)
            self.finish_edit_button.setEnabled(True)
            self.cancel_edit_button.setEnabled(True)
            self._animate_state_change()

    def set_mode(self, mode: str, tone: str = "neutral") -> None:
        changed = self.mode_badge.text() != f"Mode: {mode}"
        self._mode = mode
        self.mode_badge.setText(f"Mode: {mode}")
        self.mode_badge.set_tone("info" if tone == "neutral" else tone)
        self._refresh_guidance()
        if changed:
            self._animate_state_change()

    def set_editor_state(self, text: str, tone: str = "neutral") -> None:
        changed = self.editor_badge.text() != _HeaderPill._clean_text(text)
        self._editor_text = text
        self.editor_badge.setText(text)
        self.editor_badge.set_tone("info" if tone == "neutral" else tone)
        self._refresh_guidance()
        if changed:
            self._animate_state_change()

    def set_transaction_text(self, text: str) -> None:
        self._transaction_text = text
        self.transaction_label.setText(text)
        lower = text.lower()
        if any(part in lower for part in ("failed", "conflict", "changed on another")):
            tone = "danger"
        elif any(part in lower for part in ("waiting", "finishing", "saving", "publishing", "paused", "recovery")):
            tone = "warning"
        elif any(part in lower for part in ("ready", "editing", "published")):
            tone = "success"
        else:
            tone = "info"
        self.transaction_label.set_tone(tone)
        self._refresh_guidance()

    def set_runtime_version(self, version: str) -> None:
        self.version_label.setText(
            f"Runtime: v{version}" if not version.startswith("v") else f"Runtime: {version}"
        )

    def set_sync_status(self, status: str) -> None:
        self.sync_label.setText(f"Sync: {status}")
        lower = status.lower()
        if lower in ("idle", "synced", "ready"):
            tone = "info"
        elif lower in ("failed", "error"):
            tone = "danger"
        elif lower in ("syncing", "pending"):
            tone = "warning"
        else:
            tone = "neutral"
        self.sync_label.set_tone(tone)

    # ---- UI-PROD-07 feedback API ----
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