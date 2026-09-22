# -*- coding: utf-8 -*-
"""Application feedback and operation-state primitives for Design System V2.

UI-PROD-07 separates transient application feedback from page content states:
``StateView`` remains the owner of empty/loading/error page states, while this
module owns operation feedback, busy projection, and destructive confirmation.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QVBoxLayout,
    QWidget,
)

from .foundation import Button, ButtonVariant, Dialog
from .tokens import (
    COLORS,
    COMPONENT_METRICS,
    FONT_FAMILY,
    FONT_WEIGHTS,
    RADIUS,
    SPACING,
    STATES,
    TYPOGRAPHY,
)


class FeedbackTone(str, Enum):
    """Semantic severity shared by feedback surfaces."""

    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    DANGER = "danger"


@dataclass(frozen=True)
class FeedbackRequest:
    """A presentation-only feedback command.

    Domain/service errors should be translated into this model by the owning
    application flow. The feedback layer never decides permissions or business
    validity.
    """

    message: str
    tone: FeedbackTone = FeedbackTone.INFO
    title: str = ""
    action_label: str = ""
    action_id: str = ""
    dismissible: bool = True
    timeout_ms: Optional[int] = None
    key: str = ""

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("FeedbackRequest.message must not be empty")
        if self.timeout_ms is not None and self.timeout_ms < 0:
            raise ValueError("FeedbackRequest.timeout_ms must be >= 0")
        if self.action_label and not self.action_id:
            raise ValueError("action_id is required when action_label is provided")


class FeedbackController(QObject):
    """Signal-based application feedback controller with duplicate-op guard."""

    feedback_requested = Signal(object)
    clear_requested = Signal(str)
    busy_changed = Signal(bool, str, str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._active_operation_id = ""
        self._busy_message = ""

    @property
    def is_busy(self) -> bool:
        return bool(self._active_operation_id)

    @property
    def active_operation_id(self) -> str:
        return self._active_operation_id

    def publish(self, request: FeedbackRequest) -> FeedbackRequest:
        self.feedback_requested.emit(request)
        return request

    def info(self, message: str, **kwargs) -> FeedbackRequest:
        return self.publish(FeedbackRequest(message=message, tone=FeedbackTone.INFO, **kwargs))

    def success(self, message: str, **kwargs) -> FeedbackRequest:
        return self.publish(FeedbackRequest(message=message, tone=FeedbackTone.SUCCESS, **kwargs))

    def warning(self, message: str, **kwargs) -> FeedbackRequest:
        return self.publish(FeedbackRequest(message=message, tone=FeedbackTone.WARNING, **kwargs))

    def error(self, message: str, **kwargs) -> FeedbackRequest:
        return self.publish(FeedbackRequest(message=message, tone=FeedbackTone.DANGER, **kwargs))

    def clear(self, key: str = "") -> None:
        self.clear_requested.emit(key)

    def begin_operation(self, operation_id: str, message: str = "Working…") -> bool:
        """Start one guarded operation.

        Returns ``False`` when another operation is still active. This gives
        call sites a lightweight way to prevent accidental double submit.
        """

        operation_id = operation_id.strip()
        if not operation_id:
            raise ValueError("operation_id must not be empty")
        if self.is_busy:
            return False
        self._active_operation_id = operation_id
        self._busy_message = message.strip() or "Working…"
        self.busy_changed.emit(True, operation_id, self._busy_message)
        return True

    def finish_operation(self, operation_id: str) -> bool:
        """Finish the active operation only when the token matches."""

        if not self.is_busy or operation_id != self._active_operation_id:
            return False
        previous_id = self._active_operation_id
        self._active_operation_id = ""
        self._busy_message = ""
        self.busy_changed.emit(False, previous_id, "")
        return True

    def begin_save(self, operation_id: str = "save") -> bool:
        """Canonical Save → Saving… transition."""

        return self.begin_operation(operation_id, "Saving…")

    def save_succeeded(
        self,
        operation_id: str = "save",
        *,
        message: str = "Saved ✓",
        key: str = "save",
    ) -> Optional[FeedbackRequest]:
        """Finish a guarded save and project the canonical success feedback."""

        if not self.finish_operation(operation_id):
            return None
        return self.success(message, key=key)

    def save_failed(
        self,
        operation_id: str = "save",
        *,
        message: str = "We couldn't save your changes. Please try again.",
        retry_action_id: str = "",
        key: str = "save",
    ) -> FeedbackRequest:
        """Finish the matching save and surface a recoverable, readable error."""

        self.finish_operation(operation_id)
        kwargs = {}
        if retry_action_id:
            kwargs = {"action_label": "Try again", "action_id": retry_action_id}
        return self.error(
            message,
            title="Save failed",
            key=key,
            **kwargs,
        )

    def deleted(
        self,
        *,
        message: str = "Deleted",
        undo_action_id: str = "",
        key: str = "delete",
    ) -> FeedbackRequest:
        """Canonical Delete → deleted → optional Undo feedback."""

        kwargs = {}
        if undo_action_id:
            kwargs = {
                "action_label": "Undo",
                "action_id": undo_action_id,
                "timeout_ms": 7000,
            }
        return self.success(message, key=key, **kwargs)

    def system_error(
        self,
        error: Optional[BaseException] = None,
        *,
        message: str = "We couldn't complete this action. Please try again.",
        retry_action_id: str = "",
        key: str = "system-error",
    ) -> FeedbackRequest:
        """Project a user-readable error without leaking technical exception text.

        ``error`` is intentionally not rendered. The owning flow remains
        responsible for logging/telemetry and may provide a safe translated
        ``message`` for known domain failures.
        """

        _ = error
        kwargs = {}
        if retry_action_id:
            kwargs = {"action_label": "Try again", "action_id": retry_action_id}
        return self.error(
            message,
            title="Something went wrong",
            key=key,
            **kwargs,
        )


class FeedbackHost(QFrame):
    """Inline application feedback region.

    Informational/success feedback is transient by default. Warning/error
    feedback is persistent by default so important state cannot disappear
    before the user has read it.
    """

    action_triggered = Signal(str)
    dismissed = Signal(str)

    _DEFAULT_TIMEOUTS = {
        FeedbackTone.INFO: 4500,
        FeedbackTone.SUCCESS: 3500,
        FeedbackTone.WARNING: 0,
        FeedbackTone.DANGER: 0,
    }

    def __init__(
        self,
        controller: Optional[FeedbackController] = None,
        *,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("DesignSystemFeedbackHost")
        self._controller: Optional[FeedbackController] = None
        self._current: Optional[FeedbackRequest] = None
        self._busy = False

        self._dismiss_timer = QTimer(self)
        self._dismiss_timer.setSingleShot(True)
        self._dismiss_timer.timeout.connect(self.clear_feedback)

        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self.busy_frame = QFrame(self)
        self.busy_frame.setObjectName("FeedbackBusyFrame")
        busy_layout = QHBoxLayout(self.busy_frame)
        busy_layout.setContentsMargins(
            SPACING["lg"], SPACING["sm"], SPACING["lg"], SPACING["sm"]
        )
        busy_layout.setSpacing(SPACING["sm"])
        self.busy_progress = QProgressBar(self.busy_frame)
        self.busy_progress.setRange(0, 0)
        self.busy_progress.setTextVisible(False)
        self.busy_progress.setFixedWidth(96)
        self.busy_progress.setFixedHeight(6)
        self.busy_label = QLabel("Working…", self.busy_frame)
        self.busy_label.setWordWrap(True)
        busy_layout.addWidget(self.busy_progress)
        busy_layout.addWidget(self.busy_label, 1)
        self.busy_frame.hide()
        root.addWidget(self.busy_frame)

        self.feedback_frame = QFrame(self)
        self.feedback_frame.setObjectName("FeedbackMessageFrame")
        feedback_layout = QHBoxLayout(self.feedback_frame)
        feedback_layout.setContentsMargins(
            SPACING["lg"], SPACING["sm"], SPACING["lg"], SPACING["sm"]
        )
        feedback_layout.setSpacing(SPACING["md"])

        text_wrap = QWidget(self.feedback_frame)
        text_layout = QVBoxLayout(text_wrap)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(SPACING["xs"])
        self.title_label = QLabel("", text_wrap)
        self.title_label.setObjectName("FeedbackTitle")
        self.title_label.setWordWrap(True)
        self.message_label = QLabel("", text_wrap)
        self.message_label.setObjectName("FeedbackMessage")
        self.message_label.setWordWrap(True)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.message_label)
        feedback_layout.addWidget(text_wrap, 1)

        self.action_button = Button("", variant=ButtonVariant.SECONDARY, size="sm", parent=self.feedback_frame)
        self.action_button.clicked.connect(self._emit_action)
        self.action_button.hide()
        feedback_layout.addWidget(self.action_button)

        self.dismiss_button = Button("Close", variant=ButtonVariant.GHOST, size="sm", parent=self.feedback_frame)
        self.dismiss_button.clicked.connect(self.clear_feedback)
        feedback_layout.addWidget(self.dismiss_button)
        self.feedback_frame.hide()
        root.addWidget(self.feedback_frame)

        self.setStyleSheet(
            f"""
            QFrame#DesignSystemFeedbackHost {{
                background: transparent;
                border: none;
            }}
            QFrame#FeedbackBusyFrame {{
                background-color: {COLORS['blue_50']};
                border: none;
                border-bottom: {COMPONENT_METRICS['border_width']}px solid {COLORS['action_primary']};
            }}
            QFrame#FeedbackBusyFrame QLabel {{
                color: {COLORS['text_secondary']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['medium']};
                border: none;
            }}
            QFrame#FeedbackBusyFrame QProgressBar {{
                background-color: {COLORS['surface_card']};
                border: none;
                border-radius: {RADIUS['pill']}px;
            }}
            QFrame#FeedbackBusyFrame QProgressBar::chunk {{
                background-color: {COLORS['action_primary']};
                border-radius: {RADIUS['pill']}px;
            }}
            """
        )
        self.hide()

        if controller is not None:
            self.bind(controller)

    @property
    def current_feedback(self) -> Optional[FeedbackRequest]:
        return self._current

    @property
    def is_busy(self) -> bool:
        return self._busy

    def bind(self, controller: FeedbackController) -> None:
        if self._controller is controller:
            return
        if self._controller is not None:
            try:
                self._controller.feedback_requested.disconnect(self.show_feedback)
                self._controller.clear_requested.disconnect(self._clear_for_key)
                self._controller.busy_changed.disconnect(self._set_busy)
            except (RuntimeError, TypeError):
                pass
        self._controller = controller
        controller.feedback_requested.connect(self.show_feedback)
        controller.clear_requested.connect(self._clear_for_key)
        controller.busy_changed.connect(self._set_busy)

    def show_feedback(self, request: FeedbackRequest) -> None:
        if not isinstance(request, FeedbackRequest):
            raise TypeError("FeedbackHost.show_feedback expects FeedbackRequest")

        self._dismiss_timer.stop()
        self._current = request
        self.title_label.setText(request.title)
        self.title_label.setVisible(bool(request.title))
        self.message_label.setText(request.message)

        palette = STATES[request.tone.value]
        self.feedback_frame.setStyleSheet(
            f"""
            QFrame#FeedbackMessageFrame {{
                background-color: {palette['background']};
                border: none;
                border-bottom: {COMPONENT_METRICS['border_width']}px solid {palette['border']};
            }}
            QLabel#FeedbackTitle {{
                color: {palette['foreground']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['semibold']};
                border: none;
            }}
            QLabel#FeedbackMessage {{
                color: {COLORS['text_secondary']};
                font-family: {FONT_FAMILY};
                font-size: {TYPOGRAPHY['body_small']}px;
                font-weight: {FONT_WEIGHTS['regular']};
                border: none;
            }}
            """
        )

        self.action_button.setText(request.action_label)
        self.action_button.setVisible(bool(request.action_label))
        self.dismiss_button.setVisible(request.dismissible)
        self.feedback_frame.show()
        self._sync_visibility()

        timeout_ms = (
            self._DEFAULT_TIMEOUTS[request.tone]
            if request.timeout_ms is None
            else request.timeout_ms
        )
        if timeout_ms > 0:
            self._dismiss_timer.start(timeout_ms)

    def clear_feedback(self) -> None:
        if self._current is None:
            return
        key = self._current.key
        self._dismiss_timer.stop()
        self._current = None
        self.feedback_frame.hide()
        self.dismissed.emit(key)
        self._sync_visibility()

    def _clear_for_key(self, key: str) -> None:
        if self._current is None:
            return
        if not key or self._current.key == key:
            self.clear_feedback()

    def _set_busy(self, busy: bool, _operation_id: str, message: str) -> None:
        self._busy = busy
        self.busy_label.setText(message or "Working…")
        self.busy_frame.setVisible(busy)
        self._sync_visibility()

    def _emit_action(self) -> None:
        if self._current is None or not self._current.action_id:
            return
        action_id = self._current.action_id
        self.action_triggered.emit(action_id)
        self.clear_feedback()

    def _sync_visibility(self) -> None:
        self.setVisible(self._busy or self._current is not None)


class ConfirmationDialog(Dialog):
    """Standard confirmation surface with safe destructive defaults."""

    def __init__(
        self,
        title: str,
        message: str,
        *,
        confirm_text: str = "Confirm",
        cancel_text: str = "Cancel",
        dangerous: bool = False,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(
            title=title,
            description=message,
            primary_text=confirm_text,
            cancel_text=cancel_text,
            show_cancel=True,
            parent=parent,
        )
        if dangerous:
            self.primary_button.set_variant(ButtonVariant.DANGER)
            # Destructive confirmations must never become the accidental
            # Enter-key default. Cancel is deliberately the safe default.
            self.primary_button.setAutoDefault(False)
            self.primary_button.setDefault(False)
            self.cancel_button.setAutoDefault(True)
            self.cancel_button.setDefault(True)
        else:
            self.primary_button.setAutoDefault(True)
            self.primary_button.setDefault(True)
            self.cancel_button.setAutoDefault(False)
            self.cancel_button.setDefault(False)


__all__ = [
    "ConfirmationDialog",
    "FeedbackController",
    "FeedbackHost",
    "FeedbackRequest",
    "FeedbackTone",
]
