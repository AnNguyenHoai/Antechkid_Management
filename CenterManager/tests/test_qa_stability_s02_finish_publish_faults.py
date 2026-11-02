"""QA-S02 R4 — Finish Editing publish failures preserve SQLCipher journal.

Directly exercises production WriteTransactionManager._publish after a durable
SQLCipher commit, with isolated existing recovery fixture and a fault at the
publication transport boundary. No external remotes or real credentials.
"""
from types import SimpleNamespace

import pytest

from tests.test_e1b1_durable_write_recovery import (
    workspace, begin, mutate, values,  # noqa: F401
)
from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
from centermanager.platform.write_recovery import RecoveryRequired, WriteRecoveryJournal


@pytest.mark.parametrize("outcome", ["transport-returned-false", "transport-raised"])
def test_finish_publish_failure_keeps_committed_sqlcipher_and_recovery(
    workspace, monkeypatch, outcome
):
    begin(workspace)
    mutate(workspace)
    tx = WriteTransactionManager(SimpleNamespace())
    tx._state = WriteTransactionState.LOCAL_SAVED
    tx._recovery_journal = workspace.journal

    def failed_push():
        if outcome == "transport-raised":
            raise OSError("QA disconnected during Finish Editing Git push")
        return False

    monkeypatch.setattr(tx, "_do_publish", failed_push)
    assert tx._publish() is False

    recovered = WriteRecoveryJournal()
    receipt = recovered.inspect()
    assert receipt["status"] == "PUBLISHING"
    assert receipt["publication"] == "UNVERIFIED"
    assert tx.state == (
        WriteTransactionState.RECOVERY_REQUIRED
        if outcome == "transport-raised"
        else WriteTransactionState.FAILED
    )
    recovered.verify_capture(receipt["last_capture"])
    with pytest.raises(RecoveryRequired):
        recovered.assert_replaceable()
    assert values(recovered.database) == ["BASE", "LOCAL_UNACCEPTED"]
    assert workspace.provider.observe_remote_main_commit() == workspace.base
