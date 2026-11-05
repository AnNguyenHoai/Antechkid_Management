"""RV-02 background mirror worker: no UI disk wait, bounded queue, safe drain.

The source of truth is the committed SQLCipher outbox; these tests prove that
worker IO never becomes part of a successful user Save transaction.
"""
from __future__ import annotations

import threading
import time
from pathlib import Path

from centermanager.platform import recovery_change_mirror
from centermanager.platform.recovery_mirror_worker import _MirrorWorker


def test_enqueue_is_nonblocking_while_disk_is_stalled(tmp_path, monkeypatch):
    from centermanager.database.encryption import DatabaseKeyStore

    started = threading.Event()
    release = threading.Event()
    processed = []

    def stalled_mirror(payload, *, recovery_root, encryption_key):
        started.set()
        assert release.wait(4), "test did not release blocked disk"
        processed.append(payload)

    monkeypatch.setattr(DatabaseKeyStore, "load", lambda self: bytes(range(32)))
    monkeypatch.setattr(recovery_change_mirror, "mirror_committed_payload", stalled_mirror)
    worker = _MirrorWorker(max_pending=4)
    try:
        before = time.perf_counter()
        assert worker.enqueue(tmp_path, b"COMMITTED")
        elapsed = time.perf_counter() - before
        assert elapsed < 0.5, "Save may not synchronously wait for mirror disk IO"
        assert started.wait(2)
        assert not worker.drain(timeout_seconds=0.01), "Incomplete worker must not report complete"
    finally:
        release.set()
    assert worker.drain(timeout_seconds=5)
    assert processed == [b"COMMITTED"]
    assert worker.snapshot() == {
        "submitted": 1, "completed": 1, "failed": 0, "queued": 0,
    }


def test_queue_overflow_keeps_outbox_source_and_marks_incomplete(tmp_path, monkeypatch):
    from centermanager.database.encryption import DatabaseKeyStore

    started = threading.Event()
    release = threading.Event()

    def stalled_mirror(payload, *, recovery_root, encryption_key):
        started.set()
        assert release.wait(4)

    monkeypatch.setattr(DatabaseKeyStore, "load", lambda self: bytes(range(32)))
    monkeypatch.setattr(recovery_change_mirror, "mirror_committed_payload", stalled_mirror)
    worker = _MirrorWorker(max_pending=1)
    try:
        assert worker.enqueue(tmp_path, b"COMMITTED-1")
        assert started.wait(2)
        assert worker.enqueue(tmp_path, b"COMMITTED-2")
        assert not worker.enqueue(tmp_path, b"COMMITTED-3")
    finally:
        release.set()
    assert not worker.drain(timeout_seconds=5)
    assert worker.snapshot()["failed"] == 1


def test_failed_worker_does_not_claim_complete(tmp_path, monkeypatch):
    from centermanager.database.encryption import DatabaseKeyStore

    def unavailable_disk(*args, **kwargs):
        raise OSError("test injected access failure")

    monkeypatch.setattr(DatabaseKeyStore, "load", lambda self: bytes(range(32)))
    monkeypatch.setattr(recovery_change_mirror, "mirror_committed_payload", unavailable_disk)
    worker = _MirrorWorker(max_pending=2)
    assert worker.enqueue(tmp_path, b"COMMITTED")
    assert not worker.drain(timeout_seconds=5)
    stats = worker.snapshot()
    assert stats["completed"] == stats["submitted"] == stats["failed"] == 1


def test_worker_receives_only_immutable_bytes_and_root(tmp_path, monkeypatch):
    from centermanager.database.encryption import DatabaseKeyStore

    done = []
    monkeypatch.setattr(DatabaseKeyStore, "load", lambda self: bytes(range(32)))
    monkeypatch.setattr(
        recovery_change_mirror, "mirror_committed_payload",
        lambda payload, *, recovery_root, encryption_key: done.append(
            (payload, Path(recovery_root), encryption_key)
        ),
    )
    worker = _MirrorWorker()
    original = bytearray(b"event")
    assert worker.enqueue(tmp_path, original)
    original[:] = b"xxxxx"
    assert worker.drain(timeout_seconds=5)
    assert done == [(b"event", tmp_path, bytes(range(32)))]


def test_publish_drains_before_existing_wal_consistent_capture():
    """Static contract: never replace the recovery snapshot with a mirror-only check."""
    import ast
    source = (
        Path(__file__).resolve().parents[1]
        / "src" / "centermanager" / "services" / "write_transaction.py"
    ).read_text(encoding="utf-8-sig")
    tree = ast.parse(source)
    publish = next(
        fn for fn in ast.walk(tree)
        if isinstance(fn, ast.FunctionDef) and fn.name == "_publish"
    )
    calls = sorted(
        (c for c in ast.walk(publish) if isinstance(c, ast.Call)),
        key=lambda c: (c.lineno, c.col_offset),
    )
    drains = [c.lineno for c in calls if isinstance(c.func, ast.Name)
              and c.func.id == "timed_call"
              and c.args and isinstance(c.args[0], ast.Constant)
              and c.args[0].value == "rv02_mirror_drain"]
    captures = [c.lineno for c in calls if isinstance(c.func, ast.Name)
                and c.func.id == "timed_call"
                and c.args and isinstance(c.args[0], ast.Constant)
                and c.args[0].value == "capture_before_publish"]
    assert len(drains) == len(captures) == 1
    assert drains[0] < captures[0]


def test_mirror_worker_has_no_database_engine_imports():
    """No new connection or Git credential must be opened in background worker."""
    import ast
    path = (
        Path(__file__).resolve().parents[1]
        / "src" / "centermanager" / "platform" / "recovery_mirror_worker.py"
    )
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    imports = [
        imported.name
        for n in ast.walk(tree)
        if isinstance(n, ast.Import)
        for imported in n.names
    ] + [
        n.module or ""
        for n in ast.walk(tree)
        if isinstance(n, ast.ImportFrom)
    ]
    assert not any("sqlalchemy" in name or "git" in name.lower()
                   for name in imports)
