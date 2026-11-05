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
