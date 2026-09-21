"""EP-PROD-06 Backup/Restore Disaster Recovery UAT contract tests."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "EP-PROD-06_BACKUP_RESTORE_DISASTER_RECOVERY_UAT.md"
COLLECTOR = ROOT / "scripts" / "capture_backup_restore_dr_evidence.ps1"
VERIFIER = ROOT / "scripts" / "verify_backup_restore_dr_uat.py"
BACKUP_SERVICE = ROOT / "src" / "centermanager" / "platform" / "backup" / "backup_service.py"
STARTUP_SYNC = ROOT / "src" / "centermanager" / "platform" / "sync" / "startup_sync.py"

REQUIRED_SCENARIOS = (
    "baseline_backup_create",
    "backup_integrity",
    "restore_after_runtime_damage",
    "metadata_restore",
    "restart_after_restore",
    "corrupt_database_rejected",
    "checksum_mismatch_rejected",
    "outside_path_rejected",
    "newer_format_rejected",
    "collaboration_source_of_truth_preserved",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_verifier():
    spec = importlib.util.spec_from_file_location("ep_prod_06_verifier", VERIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _evidence() -> dict:
    sha = "4" * 64
    return {
        "schema_version": 1,
        "task": "EP-PROD-06",
        "stage": "final",
        "release": {"version": "1.0.0-rc1", "source_commit": "1" * 40},
        "backup": {
            "managed_path": True,
            "format_version": 2,
            "manifest_sha256": "5" * 64,
            "database_sha256": sha,
            "manifest_database_sha256": sha,
            "checksum_matches": True,
            "sqlite_integrity": "ok",
            "metadata_present": True,
        },
        "runtime": {
            "database_sha256": sha,
            "matches_selected_backup": True,
            "restore_temp_artifact_count": 0,
        },
    }


def _scenarios() -> dict:
    return {
        "schema_version": 1,
        "task": "EP-PROD-06",
        "scenarios": [{"scenario": name, "status": "PASS"} for name in REQUIRED_SCENARIOS],
    }


def test_prod_06_runbook_covers_destructive_recovery_and_rejection_paths():
    source = _read(DOC)
    for phrase in (
        "Restore after runtime damage",
        "Metadata restore",
        "Restart after restore",
        "Corrupt database rejected",
        "Checksum mismatch rejected",
        "Outside path rejected",
        "Newer format rejected",
        "Collaboration source of truth preserved",
        "isolated UAT",
        "failed production gate",
    ):
        assert phrase in source
    for scenario in REQUIRED_SCENARIOS:
        assert scenario in source


def test_prod_06_collector_is_read_only_and_records_integrity_evidence():
    source = _read(COLLECTOR)
    assert "Get-FileHash" in source
    assert "PRAGMA integrity_check" in source
    assert "runtime\\Backup\\publish" not in source  # composed from runtime + Backup\\publish
    assert "Backup\\publish" in source
    assert "managed_path" in source
    assert "checksum_matches" in source
    assert "restore_temp_artifact_count" in source
    assert "Set-Content" in source  # evidence output only
    assert "restore_backup" not in source.lower()
    assert "Copy-Item" not in source
    assert "Remove-Item" not in source


def test_prod_06_verifier_accepts_converged_restored_evidence():
    verifier = _load_verifier()
    report = verifier.verify_evidence(_evidence(), _scenarios())
    assert report.status == "PASSED"
    assert report.task == "EP-PROD-06"
    assert report.scenarios == REQUIRED_SCENARIOS


@pytest.mark.parametrize(
    "mutator, expected",
    [
        (lambda e, s: e["backup"].update(managed_path=False), "outside the managed backup directory"),
        (lambda e, s: e["backup"].update(sqlite_integrity="corrupt"), "SQLite integrity is not ok"),
        (lambda e, s: e["backup"].update(checksum_matches=False), "checksum does not match"),
        (lambda e, s: e["runtime"].update(database_sha256="8" * 64), "database hash differs"),
        (lambda e, s: e["runtime"].update(restore_temp_artifact_count=1), "temporary artifacts remain"),
        (lambda e, s: s["scenarios"][0].update(status="FAIL"), "not fully PASS"),
    ],
)
def test_prod_06_verifier_fails_closed(mutator, expected):
    verifier = _load_verifier()
    evidence = _evidence()
    scenarios = _scenarios()
    mutator(evidence, scenarios)
    with pytest.raises(verifier.DisasterRecoveryUATError, match=expected):
        verifier.verify_evidence(evidence, scenarios)


def test_prod_06_verifier_rejects_duplicate_or_missing_scenarios():
    verifier = _load_verifier()
    scenarios = _scenarios()
    scenarios["scenarios"].append({"scenario": REQUIRED_SCENARIOS[0], "status": "PASS"})
    with pytest.raises(verifier.DisasterRecoveryUATError, match="more than once"):
        verifier.verify_evidence(_evidence(), scenarios)


def test_prod_06_verifier_source_compiles():
    source = _read(VERIFIER)
    compile(source, str(VERIFIER), "exec")
    assert "EP-PROD-06 BACKUP/RESTORE DISASTER RECOVERY UAT: PASSED" in source
    assert "EP-PROD-06 BACKUP/RESTORE DISASTER RECOVERY UAT: FAILED" in source


def test_prod_06_existing_backup_service_has_required_safety_building_blocks():
    source = _read(BACKUP_SERVICE)
    for marker in (
        "FORMAT_VERSION = 2",
        "PRAGMA integrity_check",
        "Database checksum mismatch",
        "Backup path is outside the managed backup directory",
        "Backup format is newer than this application supports",
        "os.replace(db_tmp, paths.database_dir / \"center.db\")",
        "refresh_runtime_db()",
    ):
        assert marker in source

    startup = _read(STARTUP_SYNC)
    assert "Always reset local to remote" in startup
    assert "Always apply repository database to runtime" in startup
