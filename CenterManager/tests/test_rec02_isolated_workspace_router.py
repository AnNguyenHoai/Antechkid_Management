"""REC-02: isolated runtime routing retains all old business and recovery bytes."""
import json
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.isolated_workspace_router import (
    WorkspaceIsolationError,
    accept_isolated_runtime,
    prepare_isolated_runtime,
    read_selected_workspace,
)


@pytest.fixture
def legacy(tmp_path):
    old = tmp_path / "runtime"
    config = old / "Config"
    config.mkdir(parents=True)
    (config / "config.json").write_text('{"git":{"repository_url":"fixture"}}')
    (config / "database_key.dpapi").write_bytes(b"sealed")
    (config / "authoritative_database_identity.json").write_bytes(b"pin")
    database = old / "Database"
    database.mkdir()
    (database / "center.db").write_bytes(b"unpublished")
    (database / "center.db-wal").write_bytes(b"unpublished-wal")
    recovery = tmp_path / "runtime.write-recovery"
    recovery.mkdir()
    (recovery / "journal.json").write_bytes(b'{"status":"OPEN"}')
    return SimpleNamespace(
        project_root=tmp_path, runtime_root=old,
        old=old, recovery=recovery,
    )


def test_isolation_preserves_old_db_wal_git_and_recovery_without_routing_change(legacy):
    new = prepare_isolated_runtime(legacy)
    assert new.original == legacy.old
    assert (new.candidate / "Config" / "database_key.dpapi").read_bytes() == b"sealed"
    assert not (new.candidate / "Database" / "center.db").exists()
    assert not (new.candidate / "repository").exists()
    assert not (new.candidate.with_name(new.candidate.name + ".write-recovery")).exists()
    assert (legacy.old / "Database" / "center.db").read_bytes() == b"unpublished"
    assert (legacy.old / "Database" / "center.db-wal").read_bytes() == b"unpublished-wal"
    assert (legacy.recovery / "journal.json").read_bytes() == b'{"status":"OPEN"}'
    assert read_selected_workspace(legacy.project_root) == (None, ())


def test_atomic_select_only_after_caller_accepts_main(legacy):
    new = prepare_isolated_runtime(legacy)
    selected = accept_isolated_runtime(legacy.project_root, new)
    assert selected == new.candidate
    active, old = read_selected_workspace(legacy.project_root)
    assert active == new.candidate
    assert old == (legacy.old,)
    assert (legacy.recovery / "journal.json").read_bytes() == b'{"status":"OPEN"}'


def test_failed_routing_does_not_override_current_generation(legacy):
    first = prepare_isolated_runtime(legacy)
    accept_isolated_runtime(legacy.project_root, first)
    second = prepare_isolated_runtime(legacy)
    with pytest.raises(WorkspaceIsolationError, match="concurrently"):
        accept_isolated_runtime(legacy.project_root, second)
    assert read_selected_workspace(legacy.project_root)[0] == first.candidate


def test_selection_rejects_outside_path_and_symlink(legacy):
    marker = legacy.project_root / ".centermanager-active-runtime.json"
    marker.write_text(json.dumps({
        "format": 1,
        "active_name": "../untrusted",
        "retained_roots": ["runtime"],
    }))
    with pytest.raises(WorkspaceIsolationError):
        read_selected_workspace(legacy.project_root)


def test_unfinished_candidate_cannot_change_restart_workspace(legacy):
    prepare_isolated_runtime(legacy)
    assert read_selected_workspace(legacy.project_root)[0] is None
