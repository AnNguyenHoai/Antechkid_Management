"""Recovery receipt cannot veto a previously verified WRITE handoff."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.services.write_transaction import (
    WriteTransactionManager, WriteTransactionState,
)


class Journal:
    def __init__(self, *, fail=False):
        self.database = SimpleNamespace(exists=lambda: True)
        self.repository = Path("/temporary")
        self.fail = fail
        self.calls = []

    def begin(self, session_id, base_oid, authority, *, advisory=False):
        self.calls.append(("begin", session_id, base_oid, authority, advisory))
        if self.fail:
            raise OSError("advisory journal directory unwritable")


@pytest.mark.parametrize("old_receipt,log_fails", [
    (True, False), (False, False), (True, True), (False, True),
])
def test_verified_handoff_can_begin_even_if_recovery_log_fails(
    monkeypatch, old_receipt, log_fails,
):
    from centermanager.platform import write_recovery
    from centermanager.database import encryption

    journal = Journal(fail=log_fails)
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: journal)
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: True)
    provider = SimpleNamespace(_owned_lock_token={
        "session_id": "session", "oid": "lock-oid", "lease_revision": 2,
    })
    manager = WriteTransactionManager(SimpleNamespace(
        _sync_provider=provider, get_session_id=lambda: "session",
    ))
    manager._base_main_commit = "accepted-main"
    if old_receipt:
        manager._pre_handoff_clean_receipt = {"status": "CLEAN"}

    assert manager._begin_recovery_journal() is True
    assert len(journal.calls) == 1
    assert journal.calls[0][0] == "begin"
    assert journal.calls[0][-1] is True
    assert manager._pre_handoff_clean_receipt is None
    assert manager._recovery_journal is (None if log_fails else journal)
    assert manager.state is not WriteTransactionState.RECOVERY_REQUIRED
