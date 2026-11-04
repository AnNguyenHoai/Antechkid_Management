"""Fresh unzip must not be mistaken for a legacy WRITE workspace."""
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.sync.startup_sync import StartupSynchronization


def make_workspace(tmp_path):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    repo = runtime / "repository"
    dbdir = runtime / "Database"
    attachments = runtime / "Attachment"
    reports = runtime / "Reports"
    exports = runtime / "Export"
    recovery = tmp_path / "runtime.write-recovery"
    for path in (repo, dbdir, attachments, reports, exports, recovery):
        path.mkdir()
    journal = SimpleNamespace(
        root=recovery,
        _workspace_roots=lambda: {
            "database": dbdir,
            "attachments": attachments,
            "legacy-attachments": runtime / "Attachments",
            "reports": reports,
            "exports": exports,
        },
    )
    sync = StartupSynchronization.__new__(StartupSynchronization)
    sync._repo_path = repo
    sync._runtime_db_path = dbdir / "center.db"
    return sync, journal, runtime


def test_fresh_unzip_accepts_empty_recovery_directories_and_derived_reports(tmp_path):
    sync, journal, runtime = make_workspace(tmp_path)
    (runtime / "Reports" / "student.pdf").write_bytes(b"derived-pdf")
    (runtime / "Export" / "report.json").write_text("{}")
    (runtime / "Database" / ".gitkeep").write_text("")
    (journal.root / "captures").mkdir()
    assert sync._fresh_install_eligible(journal) is True


@pytest.mark.parametrize("path", [
    "Database/center.db",
    "Database/center.db-wal",
    "Attachment/orphan.pdf",
    "Attachments/orphan.bin",
    "repository/.git/HEAD",
    "../runtime.write-recovery/journal.json",
    "../runtime.write-recovery/captures/orphan.db",
])
def test_existing_authoritative_or_recovery_material_blocks_fresh_receipt(tmp_path, path):
    sync, journal, runtime = make_workspace(tmp_path)
    artifact = (runtime / path).resolve()
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(b"protected")
    assert sync._fresh_install_eligible(journal) is False
