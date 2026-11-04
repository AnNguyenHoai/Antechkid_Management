"""WRITE handoff must reseal only the prevalidated CLEAN state before editing."""
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

    def refresh_verified_bootstrap_migration(self, *, provider, before):
        self.calls.append(("reseal", provider, before))
        if self.fail:
            raise RuntimeError("MAIN changed")

    def begin(self, session_id, base_oid, authority):
        self.calls.append(("begin", session_id, base_oid, authority))


@pytest.mark.parametrize("has_clean_receipt,fail", [
    (True, False), (False, False), (True, True),
])
def test_handoff_does_not_begin_before_verified_receipt(
    monkeypatch, has_clean_receipt, fail
):
    from centermanager.platform import write_recovery as recovery
    from centermanager.database import encryption

    journal = Journal(fail=fail)
    monkeypatch.setattr(recovery, "WriteRecoveryJournal", lambda: journal)
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: True)
    provider = SimpleNamespace(_owned_lock_token={
        "session_id": "session", "oid": "lock-oid", "lease_revision": 2
    })
    manager = WriteTransactionManager(SimpleNamespace(
        _sync_provider=provider, get_session_id=lambda: "session"
    ))
    manager._base_main_commit = "accepted-main"
    if has_clean_receipt:
        manager._pre_handoff_clean_receipt = {"status": "CLEAN"}

    assert manager._begin_recovery_journal() is (not fail)
    names = [call[0] for call in journal.calls]
    if fail:
        assert names == ["reseal"]
        assert manager.state is WriteTransactionState.RECOVERY_REQUIRED
    elif has_clean_receipt:
        assert names == ["reseal", "begin"]
        assert manager._pre_handoff_clean_receipt is None
    else:
        assert names == ["begin"]
