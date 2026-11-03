"""QA-S01 R2: encrypted capture authenticity and journal survival tests.

The E1B1 workspace fixture uses synthetic SQLCipher credentials, temp runtime
and a disposable bare Git remote. No production data or WRITE leases.
"""
from pathlib import Path

import pytest

from tests.test_e1b1_durable_write_recovery import workspace, begin, mutate, values  # noqa: F401
from centermanager.platform.write_recovery import RecoveryRequired, WriteRecoveryJournal


def test_capture_ciphertext_tamper_is_rejected_without_changing_live_data(workspace):
    begin(workspace)
    mutate(workspace)
    journal = workspace.journal
    capture = journal.preserve("qa-s01-authenticity")
    journal.verify_capture(capture)
    live_before = values(journal.database)

    ciphertext = capture / "center.db"
    original = ciphertext.read_bytes()
    assert original
    ciphertext.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    with pytest.raises(RecoveryRequired):
        journal.verify_capture(capture)
    assert values(journal.database) == live_before
    with pytest.raises(RecoveryRequired):
        journal.assert_replaceable()


def test_new_journal_instance_preserves_before_git_main_wins_on_restart(workspace):
    begin(workspace)
    mutate(workspace)
    original_values = values(workspace.journal.database)
    assert original_values == ["BASE", "LOCAL_UNACCEPTED"]

    # Simulates losing the process-owned journal object during restart, while
    # retaining precisely the same synthetic runtime directory on disk.
    restarted_journal = WriteRecoveryJournal()
    assert restarted_journal.inspect()["status"] == "OPEN"
    with pytest.raises(RecoveryRequired):
        restarted_journal.assert_replaceable()

    from centermanager.platform.sync.startup_sync import StartupSynchronization
    sync = StartupSynchronization(workspace.provider)
    assert sync.run()
    assert values(workspace.journal.database) == ["BASE"]
    receipt = restarted_journal.inspect()
    assert receipt["status"] == "CLEAN"
    capture = receipt["last_capture"]
    restarted_journal.verify_capture(capture)
    assert values(Path(capture) / "center.db") == original_values
