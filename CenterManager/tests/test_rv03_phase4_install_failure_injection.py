"""RV-03 Phase 4: deterministic crash/replay and artifact-integrity regression.

These tests use disposable local files only. They do not replace Windows
process-kill, DPAPI or packaged EXE acceptance tests.
"""
import json
from pathlib import Path

import pytest

from centermanager.platform.sync.startup_install_replay import (
    InterruptedInstallError,
    capture_before_install,
    recover_interrupted_install,
)


def _workspace(tmp_path):
    root = tmp_path / "runtime"
    root.mkdir()
    db = root / "database" / "center.db"
    db.parent.mkdir()
    db.write_bytes(b"encrypted-synthetic-old-database")
    wal = db.with_name("center.db-wal")
    wal.write_bytes(b"committed-synthetic-wal")
    attachments = root / "attachments" / "Employees"
    attachments.mkdir(parents=True)
    (attachments / "employee.bin").write_bytes(b"original-attachment")
    manifest = root / "manifest.json"
    manifest.write_bytes(b'{"version":1}')
    absent = root / "database" / "center.db-shm"
    marker = tmp_path / "runtime.write-recovery" / "startup-install.pending.json"
    targets = [
        ("database", db), ("wal", wal), ("shm", absent),
        ("employees", attachments), ("manifest", manifest),
    ]
    return marker, targets, db, wal, attachments, manifest, absent


def test_interrupted_install_replays_all_files_and_preserves_snapshot(tmp_path):
    marker, targets, db, wal, employees, manifest, absent = _workspace(tmp_path)
    folder = capture_before_install(marker, targets, "a" * 40)
    before = [db.read_bytes(), wal.read_bytes(), (employees / "employee.bin").read_bytes(), manifest.read_bytes()]
    # Simulate process termination after an arbitrary subset was installed.
    db.write_bytes(b"new-main-db")
    wal.unlink()
    (employees / "employee.bin").write_bytes(b"new-main-attachment")
    manifest.write_bytes(b'{"version":2}')
    absent.write_bytes(b"new-shm")
    assert recover_interrupted_install(marker, targets) == "a" * 40
    assert [db.read_bytes(), wal.read_bytes(), (employees / "employee.bin").read_bytes(), manifest.read_bytes()] == before
    assert not absent.exists()
    assert not marker.exists()
    assert folder.exists()  # Never erase recovery evidence while replaying.


@pytest.mark.parametrize("damaged", ["database", "wal", "attachment"])
def test_corrupted_snapshot_blocks_all_restores_before_live_writes(tmp_path, damaged):
    marker, targets, db, wal, employees, manifest, _ = _workspace(tmp_path)
    folder = capture_before_install(marker, targets, "a" * 40)
    saved = {"database": folder / "0" / "__file__",
             "wal": folder / "1" / "__file__",
             "attachment": folder / "3" / "employee.bin"}[damaged]
    saved.write_bytes(b"CORRUPTED-SNAPSHOT")
    db.write_bytes(b"current-main-db")
    wal.write_bytes(b"current-wal")
    (employees / "employee.bin").write_bytes(b"current-attachment")
    manifest.write_bytes(b'{"version":3}')
    with pytest.raises(InterruptedInstallError):
        recover_interrupted_install(marker, targets)
    assert db.read_bytes() == b"current-main-db"
    assert wal.read_bytes() == b"current-wal"
    assert (employees / "employee.bin").read_bytes() == b"current-attachment"
    assert manifest.read_bytes() == b'{"version":3}'
    assert marker.exists()  # Manual recovery still possible.


def test_replay_rejects_changed_target_inventory_before_modifying_runtime(tmp_path):
    marker, targets, db, *_ = _workspace(tmp_path)
    capture_before_install(marker, targets, "a" * 40)
    db.write_bytes(b"installed-main-db")
    changed = list(targets)
    changed[-1] = ("manifest", tmp_path / "unrelated-manifest.json")
    with pytest.raises(InterruptedInstallError):
        recover_interrupted_install(marker, changed)
    assert db.read_bytes() == b"installed-main-db"
    assert marker.exists()


def test_replay_rejects_tampered_marker_before_modifying_runtime(tmp_path):
    marker, targets, db, *_ = _workspace(tmp_path)
    capture_before_install(marker, targets, "a" * 40)
    document = json.loads(marker.read_text(encoding="utf-8"))
    document["inventory"][0]["target"] = str(tmp_path / "other.db")
    marker.write_text(json.dumps(document), encoding="utf-8")
    db.write_bytes(b"installed-main-db")
    with pytest.raises(InterruptedInstallError):
        recover_interrupted_install(marker, targets)
    assert db.read_bytes() == b"installed-main-db"
    assert marker.exists()


def test_second_install_is_blocked_until_first_is_resolved(tmp_path):
    marker, targets, db, *_ = _workspace(tmp_path)
    capture_before_install(marker, targets, "a" * 40)
    original = db.read_bytes()
    with pytest.raises(InterruptedInstallError, match="previous"):
        capture_before_install(marker, targets, "b" * 40)
    assert marker.exists()
    assert db.read_bytes() == original
