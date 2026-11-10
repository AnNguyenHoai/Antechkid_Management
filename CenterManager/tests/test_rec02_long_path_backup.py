"""Windows MAX_PATH regression for Git MAIN pre-replacement evidence backup."""

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.manual_review_backup import (
    ManualBackupError,
    preserve_workspace_for_manual_review,
    verify_manual_review_backup,
)


def _journal(tmp_path):
    runtime = tmp_path / "runtime"
    root = tmp_path / "runtime.write-recovery"
    repository = runtime / "repository"
    nested = repository / "attachments" / ("a" * 75) / ("b" * 75)
    nested.mkdir(parents=True)
    original = nested / ("c" * 65 + ".txt")
    original.write_bytes(b"important legacy evidence")
    root.mkdir()
    return SimpleNamespace(
        root=root, runtime=runtime,
        _workspace_roots=lambda: {"repository": repository},
    ), original


def test_long_relative_path_is_flattened_and_full_original_path_retained(tmp_path):
    journal, source = _journal(tmp_path)
    archive = preserve_workspace_for_manual_review(journal, reason="startup")
    verify_manual_review_backup(archive)
    document = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    key = "repository/" + source.relative_to(journal.runtime / "repository").as_posix()
    assert document["format"] == 2
    assert key in document["files"]
    assert key in document["relocated"]
    target = archive / document["relocated"][key]
    assert "_longpaths" in target.parts
    assert target.read_bytes() == source.read_bytes()
    assert document["files"][key] == hashlib.sha256(source.read_bytes()).hexdigest()
    assert len(str(target)) < len(str(archive / key))
    assert source.read_bytes() == b"important legacy evidence"


def test_flattened_file_tampering_and_missing_file_are_detected(tmp_path):
    journal, source = _journal(tmp_path)
    archive = preserve_workspace_for_manual_review(journal, reason="startup")
    doc = json.loads((archive / "manifest.json").read_text(encoding="utf-8"))
    stored = archive / next(iter(doc["relocated"].values()))
    stored.write_bytes(b"changed")
    with pytest.raises(ManualBackupError, match="verification failed"):
        verify_manual_review_backup(archive)
    assert source.read_bytes() == b"important legacy evidence"


def test_old_v1_backups_remain_verifiable(tmp_path):
    archive = tmp_path / "archive"
    (archive / "database").mkdir(parents=True)
    (archive / "database/center.db").write_bytes(b"original")
    (archive / "manifest.json").write_text(json.dumps({
        "format": 1,
        "files": {"database/center.db": hashlib.sha256(b"original").hexdigest()},
    }), encoding="utf-8")
    verify_manual_review_backup(archive)


def test_manifest_relocation_path_cannot_escape_backup(tmp_path):
    journal, source = _journal(tmp_path)
    archive = preserve_workspace_for_manual_review(journal, reason="startup")
    manifest = archive / "manifest.json"
    doc = json.loads(manifest.read_text(encoding="utf-8"))
    key = next(iter(doc["relocated"]))
    doc["relocated"][key] = "../../outside"
    manifest.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ManualBackupError, match="verification failed"):
        verify_manual_review_backup(archive)
    assert source.exists()
