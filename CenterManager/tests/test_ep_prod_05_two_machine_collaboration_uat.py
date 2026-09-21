"""EP-PROD-05 two-machine Collaboration UAT tooling contract."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "EP-PROD-05_TWO_MACHINE_COLLABORATION_UAT.md"
COLLECTOR = ROOT / "scripts" / "capture_two_machine_uat_evidence.ps1"
VERIFIER = ROOT / "scripts" / "verify_two_machine_collaboration_uat.py"
COLLAB_TEST = ROOT / "tests" / "test_collaboration_waiting_visibility.py"
STARTUP_SYNC = ROOT / "src" / "centermanager" / "platform" / "sync" / "startup_sync.py"

REQUIRED_SCENARIOS = (
    "a_to_b_publish_sync",
    "b_to_a_publish_sync",
    "internet_loss",
    "finish_failure",
    "crash_in_write",
    "competing_lease",
    "stale_runtime",
    "restart_retry",
    "recovery_snapshot",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _load_verifier():
    spec = importlib.util.spec_from_file_location("ep_prod_05_verifier", VERIFIER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _machine(role: str, fingerprint: str) -> dict:
    return {
        "schema_version": 1,
        "task": "EP-PROD-05",
        "role": role,
        "stage": "final",
        "machine_fingerprint": fingerprint,
        "release": {
            "version": "1.0.0-rc1",
            "source_commit": "1" * 40,
        },
        "repository": {
            "available": True,
            "head": "2" * 40,
            "remote_fingerprint": "3" * 64,
            "changed_entry_count": 0,
            "clean": True,
        },
        "database": {
            "runtime_sha256": "4" * 64,
            "authoritative_sha256": "4" * 64,
            "authoritative_matches_runtime": True,
        },
        "collaboration": {"locked": False},
        "recovery": {"snapshot_count": 1, "latest_snapshot_sha256": "5" * 64},
    }


def _scenarios(status: str = "PASS") -> dict:
    return {
        "task": "EP-PROD-05",
        "scenarios": [
            {"scenario": scenario, "status": status}
            for scenario in REQUIRED_SCENARIOS
        ],
    }


def test_prod_05_manual_uat_contract_covers_required_failure_and_recovery_paths():
    source = _read(DOC)
    for phrase in (
        "A → B exact edit / publish / synchronization",
        "B → A exact edit / publish / synchronization",
        "Internet loss while READ / startup",
        "Finish/publish failure and retry",
        "Crash while holding WRITE",
        "Competing lease",
        "Stale runtime fencing",
        "Restart / retry stability",
        "Recovery snapshot evidence",
        "Git repository database remains the source of truth",
        "failed production gate",
    ):
        assert phrase in source
    for scenario in REQUIRED_SCENARIOS:
        assert scenario in source


def test_prod_05_collector_is_secret_minimizing_and_uses_bundled_git():
    source = _read(COLLECTOR)
    assert 'git\\cmd\\git.exe' in source
    assert "RELEASE_MANIFEST.json" in source
    assert "runtime\\Database\\center.db" in source
    assert "runtime\\repository" in source
    assert "database\\center.db" in source
    assert "Get-FileHash" in source
    assert "remote_fingerprint" in source
    assert "machine_fingerprint" in source
    assert "remoteUrl" in source
    # The raw remote is used only as input to SHA-256; it must not become a report field.
    report_block = source[source.index("$report = [ordered]@{"):]
    assert "remote_url =" not in report_block.lower()
    assert "computername =" not in report_block.lower()


def test_prod_05_verifier_accepts_only_converged_two_machine_pass_evidence():
    verifier = _load_verifier()
    report = verifier.verify_evidence(_machine("A", "a" * 64), _machine("B", "b" * 64), _scenarios())
    assert report.status == "PASSED"
    assert report.task == "EP-PROD-05"
    assert report.scenarios == REQUIRED_SCENARIOS


@pytest.mark.parametrize(
    "mutator, expected",
    [
        (lambda a, b, s: b["repository"].update(head="9" * 40), "HEADs have not converged"),
        (lambda a, b, s: b["database"].update(authoritative_sha256="8" * 64), "database hashes differ"),
        (lambda a, b, s: b.update(machine_fingerprint=a["machine_fingerprint"]), "same machine fingerprint"),
        (lambda a, b, s: s["scenarios"][0].update(status="FAIL"), "not fully PASS"),
    ],
)
def test_prod_05_verifier_fails_closed(mutator, expected):
    verifier = _load_verifier()
    a = _machine("A", "a" * 64)
    b = _machine("B", "b" * 64)
    scenarios = _scenarios()
    mutator(a, b, scenarios)
    with pytest.raises(verifier.TwoMachineUATError, match=expected):
        verifier.verify_evidence(a, b, scenarios)


def test_prod_05_verifier_cli_source_compiles():
    source = _read(VERIFIER)
    compile(source, str(VERIFIER), "exec")
    assert "EP-PROD-05 TWO-MACHINE COLLABORATION UAT: PASSED" in source
    assert "EP-PROD-05 TWO-MACHINE COLLABORATION UAT: FAILED" in source


def test_prod_05_building_blocks_remain_covered_by_existing_runtime_contracts():
    collaboration_source = _read(COLLAB_TEST)
    assert "test_machine_b_sees_machine_a_lock" in collaboration_source
    assert "test_release_becomes_visible_cross_machine" in collaboration_source
    assert "test_lease_renewal_remains_visible_cross_machine" in collaboration_source
    assert "test_expired_lease_becomes_visible_cross_machine" in collaboration_source
    assert "test_main_isolation_cross_machine" in collaboration_source

    startup_source = _read(STARTUP_SYNC)
    assert "if not repo_db.exists():" in startup_source
    assert "return False" in startup_source
    assert "Startup synchronization completed successfully" in startup_source
