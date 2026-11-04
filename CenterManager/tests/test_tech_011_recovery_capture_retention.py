# -*- coding: utf-8 -*-
"""TECH-011: bounded recovery captures (PO decision D-010).

* captures do not copy ``.git/objects`` content or content-addressed finance
  vouchers, yet the captured repository still resolves HEAD;
* fingerprints do not re-read immutable vouchers;
* captures of old CLEAN sessions are pruned, everything uncertain is kept.
"""
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.write_recovery import (
    CAPTURE_RETENTION_SESSIONS,
    WriteRecoveryJournal,
    _capture_hashes,
    _capture_ignore,
    _excluded_from_capture,
    _is_immutable_attachment,
)

SHA = "a" * 64


def _paths(tmp_path):
    runtime = tmp_path / "runtime"
    for sub in ("Database", "metadata", "Attachment", "repository"):
        (runtime / sub).mkdir(parents=True, exist_ok=True)
    return SimpleNamespace(
        runtime_root=runtime,
        database_dir=runtime / "Database",
        metadata_dir=runtime / "metadata",
        attachment_dir=runtime / "Attachment",
        export_dir=runtime / "Export",
        reports_dir=runtime / "Reports",
    )


def test_exclusion_rules():
    assert _excluded_from_capture("repository", ".git/objects/ab/cdef")
    assert not _excluded_from_capture("repository", ".git/HEAD")
    assert not _excluded_from_capture("repository", "database/center.db")
    assert _is_immutable_attachment("repository", f"Attachments/Finance/2026/11/{SHA}.pdf")
    assert _is_immutable_attachment("attachments", f"Finance/2026/11/{SHA}.jpg")
    assert not _is_immutable_attachment("attachments", "Finance/2026/11/receipt.pdf")
    assert not _is_immutable_attachment("attachments", f"Employees/EMP-1/{SHA}.pdf")
    assert not _is_immutable_attachment("database", f"Finance/{SHA}.pdf")


@pytest.mark.skipif(shutil.which("git") is None, reason="git is required")
def test_capture_without_object_content_still_resolves_head(tmp_path):
    repo = tmp_path / "repository"
    repo.mkdir()
    env = dict(os.environ, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    (repo / "database").mkdir()
    (repo / "database" / "center.db").write_bytes(b"db")
    voucher = repo / "Attachments" / "Finance" / "2026" / "11" / f"{SHA}.pdf"
    voucher.parent.mkdir(parents=True)
    voucher.write_bytes(b"%PDF")
    subprocess.run(["git", "add", "."], cwd=repo, check=True, env=env)
    subprocess.run(["git", "commit", "-q", "-m", "x"], cwd=repo, check=True, env=env)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, check=True, capture_output=True, text=True).stdout.strip()

    capture = tmp_path / "capture"
    shutil.copytree(repo, capture, ignore=_capture_ignore("repository", repo))

    assert (capture / ".git" / "objects").is_dir()
    assert not any(p.is_file() for p in (capture / ".git" / "objects").rglob("*"))
    assert (capture / "database" / "center.db").read_bytes() == b"db"
    assert not (capture / "Attachments" / "Finance" / "2026" / "11" / f"{SHA}.pdf").exists()
    captured_head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=capture, check=True, capture_output=True, text=True).stdout.strip()
    assert captured_head == head
    # Source and copied hash sets agree on the non-excluded files.
    assert _capture_hashes("repository", repo).keys() == _capture_hashes("repository", capture).keys()


def test_fingerprint_does_not_read_immutable_vouchers(tmp_path):
    paths = _paths(tmp_path)
    voucher = paths.attachment_dir / "Finance" / "2026" / "11" / f"{SHA}.png"
    voucher.parent.mkdir(parents=True)
    voucher.write_bytes(b"12345")
    other = paths.attachment_dir / "Employees" / "cv.pdf"
    other.parent.mkdir(parents=True)
    other.write_bytes(b"cv")

    files = WriteRecoveryJournal(paths).fingerprint()

    assert files[f"attachments/Finance/2026/11/{SHA}.png"] == "immutable:5"
    assert len(files["attachments/Employees/cv.pdf"]) == 64


def _capture(journal, session_id, mtime):
    capture = journal.root / "captures" / f"{session_id}-{mtime}"
    capture.mkdir(parents=True)
    (capture / "manifest.json").write_text(json.dumps({"journal": {"session_id": session_id}}), encoding="utf-8")
    os.utime(capture, (mtime, mtime))
    return capture


def _history(journal, session_id, status):
    history = journal.root / "history"
    history.mkdir(parents=True, exist_ok=True)
    (history / f"{session_id}.json").write_text(json.dumps({"session_id": session_id, "status": status}), encoding="utf-8")


def _current(journal, session_id, last_capture=None):
    document = {"format": 1, "runtime": str(journal.runtime), "status": "OPEN", "session_id": session_id}
    if last_capture is not None:
        document["last_capture"] = str(last_capture)
    journal.journal.parent.mkdir(parents=True, exist_ok=True)
    journal.journal.write_text(json.dumps(document), encoding="utf-8")


def test_retention_keeps_newest_sessions_and_all_unsettled(tmp_path):
    journal = WriteRecoveryJournal(_paths(tmp_path))
    total = CAPTURE_RETENTION_SESSIONS + 5
    captures = {}
    for index in range(total):
        sid = f"s{index:02d}"
        captures[sid] = [_capture(journal, sid, 1_700_000_000 + index * 10 + k) for k in range(3)]
        _history(journal, sid, "CLEAN")
    # Two old sessions that did not finish cleanly must survive.
    _history(journal, "s00", "RECONCILED")
    _history(journal, "s01", "POST_PUBLISH_PENDING")
    current = _capture(journal, "current", 1_800_000_000)
    _current(journal, "current", last_capture=current)
    broken = journal.root / "captures" / "broken"
    broken.mkdir()

    deleted = journal.prune_captures()

    # Newest 20 sessions = "current" + s24..s06; s05..s02 are old and CLEAN.
    assert deleted == 4 * 3
    for sid in ("s02", "s03", "s04", "s05"):
        assert not any(c.exists() for c in captures[sid])
    for sid in ("s00", "s01"):
        assert all(c.exists() for c in captures[sid])
    for index in range(total - (CAPTURE_RETENTION_SESSIONS - 1), total):
        assert all(c.exists() for c in captures[f"s{index:02d}"])
    assert current.exists()
    assert broken.exists()


def test_retention_keeps_sessions_without_history(tmp_path):
    journal = WriteRecoveryJournal(_paths(tmp_path))
    old = [_capture(journal, f"x{i}", 1_600_000_000 + i) for i in range(CAPTURE_RETENTION_SESSIONS + 3)]
    _current(journal, "now")

    assert journal.prune_captures() == 0
    assert all(c.exists() for c in old)


def test_begin_calls_retention_without_blocking_on_failure():
    source = (Path(__file__).resolve().parents[1] / "src" / "centermanager" / "platform" / "write_recovery.py").read_text(encoding="utf-8")
    begin = source[source.index("    def begin("):source.index("    def prune_captures(")]
    assert begin.index("self.preserve('base')") < begin.index("self.prune_captures()")
    assert "except Exception:" in begin
