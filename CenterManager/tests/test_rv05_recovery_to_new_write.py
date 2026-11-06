"""RV-05 isolated Git-only recovery -> fresh WRITE -> Finish integration.

Uses synthetic encrypted SQLCipher and a disposable local bare Git remote.
Never accesses production credentials, users, repositories or lock refs.
Windows packaged-EXE and legacy-client UAT remain separate release gates.
"""
from pathlib import Path
import subprocess

from tests.test_e1b1_durable_write_recovery import (
    workspace, begin, mutate, values, git, connect,
)


def test_a_plus_ten_recovery_then_independent_write_and_finish(workspace, tmp_path, monkeypatch):
    from centermanager.platform.recovery_case_registry import RecoveryCaseRegistry
    from centermanager.platform.sync.startup_sync import StartupSynchronization
    from centermanager.platform.collaboration import CollaborationManager
    from centermanager.platform.collaboration.heartbeat import HeartbeatManager
    from centermanager.services.write_transaction import WriteTransactionManager, WriteTransactionState
    from centermanager.events.event_bus import EventBus

    w = workspace
    begin(w)
    mutate(w)
    assert values(w.journal.database) == ["BASE", "LOCAL_UNACCEPTED"]

    # An unrelated remote writer legitimately advances authoritative MAIN.
    second = tmp_path / "legitimate-remote-client"
    subprocess.run(
        ["git", "clone", "-b", "main", str(w.remote), str(second)],
        check=True, capture_output=True, text=True,
    )
    git(second, "config", "user.name", "Synthetic second client")
    git(second, "config", "user.email", "synthetic@example.invalid")
    for i in range(10):
        (second / "remote_generation.txt").write_text(str(i), encoding="utf-8")
        git(second, "add", "remote_generation.txt")
        git(second, "commit", "-m", "legitimate remote advance %d" % i)
    git(second, "push", "origin", "main")
    accepted_oid = git(second, "rev-parse", "HEAD")
    assert accepted_oid != w.base

    startup = StartupSynchronization(w.provider)
    assert startup.run()
    assert values(w.journal.database) == ["BASE"]
    registry = RecoveryCaseRegistry(w.journal)
    pending = registry.pending_cases()
    assert len(pending) == 1
    case = pending[0]
    captured_path = Path(case["capture_ref"])
    assert values(captured_path / "center.db") == ["BASE", "LOCAL_UNACCEPTED"]
    assert w.provider.observe_remote_main_commit() == accepted_oid

    # Recovery reminder is advisory. No acknowledgement is required to get
    # a freshly verified WRITE lease after the safe startup completed.
    monkeypatch.setattr(HeartbeatManager, "start", lambda self: None)
    cm = CollaborationManager(
        runtime_root=w.paths.runtime_root, event_bus=EventBus(), sync_provider=w.provider
    )
    cm.initialize("rv05-writer", "rv05-writer", "admin")
    tx = WriteTransactionManager(cm)

    class Sync:
        def execute_write_handoff_sync(self):
            return True  # Startup already installed this exact accepted MAIN.
        def get_last_write_handoff_main_commit(self):
            return w.provider.get_local_main_commit()
        def publish_only(self, message, user, expected_main_commit, repository_already_materialized=False):
            assert repository_already_materialized
            return w.provider.publish_only(message, user, expected_main_commit)

    tx.set_sync_service(Sync())
    try:
        assert tx.start_editing(), tx.last_start_error
        assert tx.state == WriteTransactionState.EDITING
        database = connect(w.journal.database)
        try:
            database.execute("INSERT INTO recovery_items(value) VALUES ('NEW_AUTHORIZED_WRITE')")
            database.commit()
        finally:
            database.close()
        tx.mark_dirty()
        assert tx.finish_editing(), tx.last_start_error
        assert tx.state == WriteTransactionState.IDLE
        new_oid = w.provider.observe_remote_main_commit()
        assert new_oid not in {w.base, accepted_oid}
        assert values(w.journal.repository / "database" / "center.db") == [
            "BASE", "NEW_AUTHORIZED_WRITE"
        ]
        # Earlier LOCAL_UNACCEPTED data must not leak into the new remote MAIN.
        assert values(captured_path / "center.db") == ["BASE", "LOCAL_UNACCEPTED"]
        assert w.journal.verify_capture(captured_path)["files"]["center.db"] == case["capture_db_sha256"]
        assert registry.get(case["case_id"])["status"] == "PENDING_REVIEW"
        assert StartupSynchronization(w.provider).run()
        assert registry.get(case["case_id"])["status"] == "PENDING_REVIEW"
        assert len(registry.list_cases()) == 1
        assert values(w.journal.database) == ["BASE", "NEW_AUTHORIZED_WRITE"]
    finally:
        cm.shutdown()
