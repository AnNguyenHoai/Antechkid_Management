"""REC-05: interruption boundaries of isolated MAIN selection and history."""
import json
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.isolated_workspace_router import (
    WorkspaceIsolationError,
    prepare_isolated_runtime,
    accept_isolated_runtime,
    read_selected_workspace,
)


def _root(root):
    config = root / "Config"
    config.mkdir(parents=True)
    (config / "config.json").write_text('{"git":{"branch":"main_repos"}}')
    (config / "database_key.dpapi").write_text("DPAPI-ciphertext")
    db = root / "Database"
    db.mkdir()
    (db / "center.db").write_bytes(b"unpublished-LOCAL")
    (db / "center.db-wal").write_bytes(b"unpublished-WAL")
    journal = root.with_name(root.name + ".write-recovery")
    journal.mkdir()
    (journal / "journal.json").write_text('{"status":"OPEN"}')
    return journal


def test_crash_before_active_marker_keeps_old_database_and_routing(tmp_path):
    old = tmp_path / "runtime"
    journal = _root(old)
    paths = SimpleNamespace(project_root=tmp_path, runtime_root=old)
    candidate = prepare_isolated_runtime(paths)
    # Simulate process termination immediately after clone/candidate allocation.
    assert read_selected_workspace(tmp_path) == (None, ())
    assert (old / "Database" / "center.db").read_bytes() == b"unpublished-LOCAL"
    assert (old / "Database" / "center.db-wal").read_bytes() == b"unpublished-WAL"
    assert (journal / "journal.json").read_text() == '{"status":"OPEN"}'
    assert candidate.candidate.is_dir()


def test_multiple_clean_main_generations_keep_all_old_recovery_roots(tmp_path):
    original = tmp_path / "runtime"
    journal = _root(original)
    first = prepare_isolated_runtime(SimpleNamespace(project_root=tmp_path, runtime_root=original))
    accept_isolated_runtime(tmp_path, first)
    # A subsequent crashed editing generation must likewise never overwrite
    # the original or the now-retired earlier MAIN runtime.
    second = prepare_isolated_runtime(SimpleNamespace(project_root=tmp_path, runtime_root=first.candidate))
    accept_isolated_runtime(tmp_path, second)
    current, old = read_selected_workspace(tmp_path)
    assert current == second.candidate
    assert old == (original, first.candidate)
    assert (journal / "journal.json").read_text() == '{"status":"OPEN"}'


@pytest.mark.parametrize("invalid", [
    "{not-json",
    json.dumps({"format": 2, "active_name": "runtime-main-" + "a" * 32, "retained_roots": []}),
    json.dumps({"format": 1, "active_name": "../../escape", "retained_roots": []}),
])
def test_broken_active_pointer_fails_closed_not_to_untrusted_runtime(tmp_path, invalid):
    _root(tmp_path / "runtime")
    (tmp_path / ".centermanager-active-runtime.json").write_text(invalid)
    with pytest.raises(WorkspaceIsolationError):
        read_selected_workspace(tmp_path)


def test_incomplete_legacy_key_copy_refuses_symlinked_secret(tmp_path):
    old = tmp_path / "runtime"
    _root(old)
    secret = old / "Config" / "database_key.dpapi"
    secret.unlink()
    secret.symlink_to(old / "Database" / "center.db")
    with pytest.raises(WorkspaceIsolationError, match="configuration"):
        prepare_isolated_runtime(SimpleNamespace(project_root=tmp_path, runtime_root=old))
    assert (old / "Database" / "center.db").read_bytes() == b"unpublished-LOCAL"
