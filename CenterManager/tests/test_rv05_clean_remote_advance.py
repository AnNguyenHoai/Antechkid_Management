"""RV-05 regression: sequential successful writers must not create Recovery.

Real disposable Git remote + SQLCipher; never touches production Git or DB.
A publishes, B publishes a successor, A starts against a newer MAIN, then
A independently obtains a new WRITE and finishes again.
"""
import subprocess

from tests.test_e1b1_durable_write_recovery import workspace, git, connect, values


def _append(path, value):
    connection = connect(path)
    try:
        connection.execute("INSERT INTO recovery_items(value) VALUES (?)", (value,))
        connection.commit()
    finally:
        connection.close()


def test_clean_a_then_b_remote_advance_then_a_startup_and_write(workspace, tmp_path, monkeypatch):
    from centermanager.database.artifact_identity import (
        next_identity_document, write_identity_document, identity_manifest_path,
    )
    from centermanager.platform.collaboration import CollaborationManager
    from centermanager.platform.collaboration.heartbeat import HeartbeatManager
    from centermanager.platform.recovery_case_registry import RecoveryCaseRegistry
    from centermanager.platform.sync.startup_sync import StartupSynchronization
    from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
    from centermanager.events.event_bus import EventBus

    w = workspace
    monkeypatch.setattr(HeartbeatManager, "start", lambda self: None)

    def open_editor(username):
        cm = CollaborationManager(
            runtime_root=w.paths.runtime_root, event_bus=EventBus(),
            sync_provider=w.provider,
        )
        cm.initialize(username, username, "admin")
        transaction = WriteTransactionManager(cm)

        class Sync:
            def execute_write_handoff_sync(self):
                return True  # Each startup already installed the exact MAIN.
            def get_last_write_handoff_main_commit(self):
                return w.provider.get_local_main_commit()
            def publish_only(self, message, user, expected_main_commit, repository_already_materialized=False):
                assert repository_already_materialized
                return w.provider.publish_only(message, user, expected_main_commit)

        transaction.set_sync_service(Sync())
        return cm, transaction

    # A's first editing session publishes normally, with a verified CLEAN
    # journal; A may then be offline while another client commits.
    first_cm, first_tx = open_editor("writer-a")
    try:
        assert first_tx.start_editing(), first_tx.last_start_error
        _append(w.journal.database, "A_FIRST")
        first_tx.mark_dirty()
        assert first_tx.finish_editing(), first_tx.last_start_error
        assert first_tx.state == WriteTransactionState.IDLE
        assert w.journal.inspect()["status"] == "CLEAN"
        first_oid = w.provider.observe_remote_main_commit()
        assert values(w.journal.database) == ["BASE", "A_FIRST"]
    finally:
        first_cm.shutdown()

    # B is a *different* Git working copy and publishes an updated, valid
    # encrypted authoritative database, not just an unrelated Git file.
    other = tmp_path / "client-b"
    subprocess.run(["git", "clone", "-b", "main", str(w.remote), str(other)],
                   check=True, capture_output=True, text=True)
    git(other, "config", "user.name", "Synthetic Writer B")
    git(other, "config", "user.email", "synthetic@example.invalid")
    other_db = other / "database" / "center.db"
    _append(other_db, "B_SECOND")
    write_identity_document(
        identity_manifest_path(other_db),
        next_identity_document(other_db, bytes(range(32)), other_db),
    )
    git(other, "add", ".")
    git(other, "commit", "-m", "synthetic B authorized successor")
    git(other, "push", "origin", "main")
    second_oid = git(other, "rev-parse", "HEAD")
    assert second_oid != first_oid
    assert git(w.journal.repository, "rev-parse", "HEAD") == first_oid
    assert w.provider.observe_remote_main_commit() == second_oid

    # A is simply behind. An authenticated CLEAN receipt must take the
    # normal MAIN synchronization path without producing a recovery case.
    assert StartupSynchronization(w.provider).run()
    assert git(w.journal.repository, "rev-parse", "HEAD") == second_oid
    assert values(w.journal.database) == ["BASE", "A_FIRST", "B_SECOND"]
    assert w.journal.inspect()["status"] == "CLEAN"
    assert RecoveryCaseRegistry(w.journal).list_cases() == []
    assert w.journal.inspect().get("rv03_case_id") is None

    # A gets a fresh remote WRITE grant, edits on top of B and finishes.
    second_cm, second_tx = open_editor("writer-a-again")
    try:
        assert second_tx.start_editing(), second_tx.last_start_error
        _append(w.journal.database, "A_THIRD")
        second_tx.mark_dirty()
        assert second_tx.finish_editing(), second_tx.last_start_error
        assert second_tx.state == WriteTransactionState.IDLE
        third_oid = w.provider.observe_remote_main_commit()
        assert third_oid not in {first_oid, second_oid}
        assert values(w.journal.repository / "database" / "center.db") == [
            "BASE", "A_FIRST", "B_SECOND", "A_THIRD",
        ]
        assert RecoveryCaseRegistry(w.journal).list_cases() == []
        assert StartupSynchronization(w.provider).run()
        assert values(w.journal.database) == [
            "BASE", "A_FIRST", "B_SECOND", "A_THIRD",
        ]
        assert RecoveryCaseRegistry(w.journal).list_cases() == []
    finally:
        second_cm.shutdown()
