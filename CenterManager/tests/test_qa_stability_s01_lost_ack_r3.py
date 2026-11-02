"""QA-S01 R3: publish ACK ambiguity with genuine SQLCipher and disposable Git.

No production remote, user database, or credentials. Verifies the on-disk
PUBLISHING state is preserved until the exact published Git OID is observed.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from tests.test_e1b1_durable_write_recovery import (
    workspace, begin, mutate, values, git, connect,  # noqa: F401
)
from centermanager.database.artifact_security import materialize_runtime_database_to_repository
from centermanager.platform.write_recovery import RecoveryRequired, WriteRecoveryJournal


def _push_while_ack_unknown(w):
    begin(w)
    mutate(w)
    materialize_runtime_database_to_repository()
    w.journal.preserve("qa-before-push")
    w.journal.update(status="PUBLISHING")
    git(w.journal.repository, "add", ".")
    git(w.journal.repository, "commit", "-m", "qa synthetic publish accepted")
    git(w.journal.repository, "push", "origin", "main")
    accepted = git(w.journal.repository, "rev-parse", "HEAD")
    assert w.provider.observe_remote_main_commit() == accepted
    return accepted


def _validate_cipher(db):
    conn = connect(db, readonly=True)
    try:
        assert conn.execute("PRAGMA integrity_check").fetchone() == ("ok",)
        assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    finally:
        conn.close()


def test_remote_accepted_but_ack_unknown_requires_exact_reobservation(workspace):
    w = workspace
    accepted = _push_while_ack_unknown(w)
    # Simulate the client losing the acknowledgement, not the push itself.
    restarted = WriteRecoveryJournal()
    assert restarted.inspect()["status"] == "PUBLISHING"
    assert restarted.inspect()["publication"] == "UNVERIFIED"
    with pytest.raises(RecoveryRequired):
        restarted.assert_replaceable()

    unknown = SimpleNamespace(
        get_local_main_commit=lambda: accepted,
        observe_remote_main_commit=lambda: None,
    )
    with pytest.raises(RecoveryRequired, match="UNKNOWN"):
        restarted.published(unknown)
    assert restarted.inspect()["status"] == "PUBLISHING"
    assert restarted.inspect()["publication"] == "UNVERIFIED"

    # Once exact accepted OID and bytes are independently observable, the
    # published receipt may be verified, but cannot become CLEAN before release.
    restarted.published(w.provider)
    assert restarted.inspect()["status"] == "PUBLISHED"
    assert restarted.inspect()["publication"] == "VERIFIED"
    with pytest.raises(RecoveryRequired):
        restarted.assert_replaceable()
    for path in (restarted.database, restarted.repository / "database" / "center.db"):
        _validate_cipher(path)
        assert values(path) == ["BASE", "LOCAL_UNACCEPTED"]
    restarted.released()
    assert restarted.inspect()["status"] == "CLEAN"
    restarted.assert_replaceable()


def test_remote_accepted_but_local_changes_after_push_never_clean(workspace):
    w = workspace
    accepted = _push_while_ack_unknown(w)
    # Any additional committed SQLCipher change after the Git publication
    # must be retained and must not be silently treated as accepted data.
    mutate(w)
    assert w.provider.observe_remote_main_commit() == accepted
    restarted = WriteRecoveryJournal()
    with pytest.raises(RecoveryRequired):
        restarted.published(w.provider)
    assert restarted.inspect()["status"] == "PUBLISHING"
    assert restarted.inspect()["publication"] == "UNVERIFIED"
    with pytest.raises(RecoveryRequired):
        restarted.assert_replaceable()
    assert values(restarted.database) == ["BASE", "LOCAL_UNACCEPTED", "LOCAL_UNACCEPTED"]
    assert values(restarted.repository / "database" / "center.db") == [
        "BASE", "LOCAL_UNACCEPTED",
    ]
