"""Safety guard for write-transaction entry.

The UI must never become inert because a previous write attempt left the
transaction in ACQUIRING. This module keeps the existing transaction manager
intact while recovering that transient state and converting request exceptions
into a clean failed acquisition.
"""

import logging
from functools import wraps

from .write_transaction import WriteTransactionState

logger = logging.getLogger(__name__)


def install_write_transaction_guard(manager_cls) -> None:
    """Install entry-state recovery once on WriteTransactionManager."""
    if getattr(manager_cls, "_entry_guard_installed", False):
        return

    original_can_edit = manager_cls.can_edit.fget
    original_start_editing = manager_cls.start_editing

    def guarded_can_edit(self):
        # ACQUIRING is transient. If no collaboration lock is actually owned,
        # the previous attempt did not complete and a new click must be allowed.
        if self._state == WriteTransactionState.ACQUIRING:
            try:
                if not self._collab_manager.is_writing():
                    logger.warning(
                        "Recovering stale ACQUIRING transaction before new edit request"
                    )
                    self._state = WriteTransactionState.IDLE
            except Exception:
                logger.exception("Failed to inspect collaboration state while recovering ACQUIRING")
        return original_can_edit(self)

    def guarded_start_editing(self, save_callback=None):
        # Recover the same stale transient state even when start_editing() is
        # called programmatically rather than through the UI property check.
        if self._state == WriteTransactionState.ACQUIRING:
            try:
                if not self._collab_manager.is_writing():
                    logger.warning("Resetting stale ACQUIRING state before start_editing")
                    self._state = WriteTransactionState.IDLE
            except Exception:
                logger.exception("Failed to inspect collaboration state before start_editing")

        try:
            return original_start_editing(self, save_callback)
        except Exception as exc:
            # Never leave the transaction stuck in ACQUIRING after an exception
            # from collaboration/sync infrastructure. MainWindow can then show
            # its normal acquisition-failed feedback and the user can retry.
            logger.exception("Write acquisition failed unexpectedly: %s", exc)
            if self._state == WriteTransactionState.ACQUIRING:
                self._state = WriteTransactionState.IDLE
            return False

    manager_cls.can_edit = property(guarded_can_edit)
    manager_cls.start_editing = guarded_start_editing
    manager_cls._entry_guard_installed = True
