# -*- coding: utf-8 -*-
"""Authoritative forced-password-change orchestration.

Password changes mutate the shared database, so production startup must publish
them through the same WRITE transaction used by the rest of CenterManager.
This module deliberately owns no Git/DB synchronization logic; it only drives
the existing WriteTransactionManager and fails closed until publication
succeeds.
"""
from __future__ import annotations

import logging
from typing import Any

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QMessageBox

from centermanager.core.current_user import set_current_user
from centermanager.platform.collaboration import WriteGranted
from centermanager.services.write_transaction import WriteTransactionState
from centermanager.ui.change_password_dialog import ChangePasswordDialog

logger = logging.getLogger(__name__)


class AuthoritativePasswordChangeCoordinator:
    """Keep the application restricted until a forced password is published."""

    def __init__(
        self,
        *,
        window,
        current_user: Any,
        permission_service,
        transaction_manager,
        collaboration_manager,
    ) -> None:
        self._window = window
        self._user_id = current_user.id
        self._permission_service = permission_service
        self._transaction = transaction_manager
        self._collaboration_manager = collaboration_manager
        self._active = bool(getattr(current_user, "force_password_change", False))
        self._dialog_open = False
        self._failure_shown = False

        self._collaboration_manager._event_bus.register(
            WriteGranted,
            self._on_write_granted,
        )

    def start(self) -> None:
        if not self._active:
            return
        self._apply_restriction(
            "Password update required. Preparing secure write access..."
        )
        self._request_write()

    def _apply_restriction(self, message: str) -> None:
        if hasattr(self._window, "central_stack"):
            self._window.central_stack.setEnabled(False)
        if hasattr(self._window, "app_top_bar"):
            self._window.app_top_bar.setEnabled(False)
            self._window.app_top_bar.set_transaction_text(message)
            self._window.app_top_bar.set_editor_state(
                "Password update required",
                "warning",
            )
        self._window.statusBar().showMessage(message)

    def _request_write(self) -> None:
        if not self._active:
            return

        if self._transaction.is_editing:
            QTimer.singleShot(0, self._open_change_dialog)
            return

        if self._transaction.state == WriteTransactionState.WAITING:
            self._apply_restriction(
                "Waiting for the current editor before updating your password..."
            )
            return

        if self._transaction.state != WriteTransactionState.IDLE:
            self._fail_closed(
                "Password update cannot start because the write transaction "
                f"is {self._transaction.state.name}."
            )
            return

        granted = self._transaction.start_editing()
        if granted:
            self._apply_restriction("Secure write access ready. Updating password...")
            QTimer.singleShot(0, self._open_change_dialog)
            return

        if self._transaction.state == WriteTransactionState.WAITING:
            self._apply_restriction(
                "Waiting for the current editor before updating your password..."
            )
            return

        self._fail_closed(
            self._transaction.last_start_error
            or "Could not acquire secure write access for the password update."
        )

    def _on_write_granted(self, event) -> None:
        if not self._active:
            return
        if event.session_id != self._collaboration_manager.get_session_id():
            return
        QTimer.singleShot(0, self._continue_after_grant)

    def _continue_after_grant(self) -> None:
        if not self._active:
            return
        if (
            self._transaction.state == WriteTransactionState.GRANTING
            or self._transaction.state == WriteTransactionState.WAITING
        ):
            self._transaction.on_write_granted()

        if self._transaction.is_editing:
            self._apply_restriction("Secure write access ready. Updating password...")
            self._open_change_dialog()

    def _open_change_dialog(self) -> None:
        if not self._active or self._dialog_open or not self._transaction.is_editing:
            return

        # Re-read after WRITE acquisition because handoff may replace runtime DB.
        fresh_user = self._permission_service.get_user(self._user_id)
        if fresh_user is None:
            self._fail_closed("The authenticated account is no longer available.")
            return

        if not fresh_user.force_password_change:
            # Another authoritative writer may have completed it while we waited.
            self._transaction.cancel_editing(force=True)
            self._complete(fresh_user)
            return

        self._dialog_open = True
        dialog = ChangePasswordDialog(fresh_user, self._permission_service)
        result = dialog.exec()
        self._dialog_open = False

        if result != ChangePasswordDialog.DialogCode.Accepted:
            self._abort_and_close(
                "Password update was cancelled. CenterManager will close "
                "without granting workspace access."
            )
            return

        # change_password() re-verifies current password against the fresh DB.
        # Finish Editing is the authoritative publication boundary.
        self._transaction.mark_dirty()
        published = self._transaction.finish_editing(
            save_callback=lambda: True,
            on_publish_success=self._on_publish_success,
            on_publish_failure=self._on_publish_failure,
        )
        if not published and not self._failure_shown:
            self._fail_closed(
                "The password was changed locally but could not be published "
                "authoritatively. Workspace access remains blocked."
            )

    def _on_publish_success(self) -> None:
        fresh_user = self._permission_service.get_user(self._user_id)
        if fresh_user is None or fresh_user.force_password_change:
            self._fail_closed(
                "Password publication completed but the authoritative account "
                "state could not be verified."
            )
            return
        self._complete(fresh_user)

    def _complete(self, user) -> None:
        set_current_user(user)
        self._window._current_user = user
        self._active = False
        if hasattr(self._window, "central_stack"):
            self._window.central_stack.setEnabled(True)
        if hasattr(self._window, "app_top_bar"):
            self._window.app_top_bar.setEnabled(True)
        self._window._update_write_buttons()
        self._window.statusBar().showMessage(
            "Password updated and published successfully.",
            5000,
        )
        logger.info(
            "Authoritative forced password change completed for user_id=%s",
            self._user_id,
        )

    def _on_publish_failure(self, error: str) -> None:
        self._fail_closed(
            "Could not publish the password update. "
            f"CenterManager will remain locked. Details: {error}"
        )

    def _fail_closed(self, message: str) -> None:
        logger.error("Forced password change failed closed: %s", message)
        self._failure_shown = True
        self._apply_restriction("Password update failed. Workspace access is blocked.")
        QMessageBox.critical(
            self._window,
            "Password Update Failed",
            message + "\n\nClose CenterManager and try again after checking connectivity.",
        )

    def _abort_and_close(self, message: str) -> None:
        logger.warning(message)
        try:
            if self._transaction.is_waiting or self._transaction.is_editing:
                self._transaction.cancel_editing(force=True)
        except Exception:
            logger.exception("Failed to release password-change WRITE transaction")
        QMessageBox.information(
            self._window,
            "Password Update Required",
            message,
        )
        QTimer.singleShot(0, self._window.close)
