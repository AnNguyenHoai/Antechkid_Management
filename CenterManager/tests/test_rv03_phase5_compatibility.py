"""RV-03 Phase 5: compatibility, evidence-binding and publication-negative tests.

Checks no case can grant remote publication or replace the wrong workspace.
Packaged legacy EXE/two-client stale-owner UAT remains a separate release gate.
"""
from threading import RLock
from types import SimpleNamespace

import pytest

from tests.test_rv03_recovery_case_registry import BASE, MAIN, FakeJournal
from centermanager.platform.recovery_case_registry import RecoveryCaseRegistry
from centermanager.platform.write_recovery import RecoveryRequired


@pytest.fixture
def case_key(monkeypatch):
    monkeypatch.setattr(RecoveryCaseRegistry, "_key", lambda self: bytes(range(32)))


def test_recovery_case_remains_pending_after_many_clean_restarts(tmp_path, case_key):
    journal = FakeJournal(tmp_path)
    initial = RecoveryCaseRegistry(journal).register_from_reconciled(observed_main_oid=MAIN)
    journal.document["status"] = "CLEAN"
    for _ in range(5):
        current = RecoveryCaseRegistry(journal).verify_pinned_case()
        assert current == initial
        assert current["status"] == "PENDING_REVIEW"
        assert current["change_log_coverage"] == "UNKNOWN"
        assert current["publication"] == "UNVERIFIED"
    assert len(RecoveryCaseRegistry(journal).list_cases()) == 1


@pytest.mark.parametrize("field,value", [
    ("repository_id", "f" * 64),
    ("base_main_oid", "f" * 40),
])
def test_pinned_case_cannot_be_reused_by_another_workspace(tmp_path, case_key, field, value):
    journal = FakeJournal(tmp_path)
    record = RecoveryCaseRegistry(journal).register_from_reconciled(observed_main_oid=MAIN)
    journal.document["status"] = "CLEAN"
    journal.document[field] = value
    with pytest.raises(RecoveryRequired, match="does not match"):
        RecoveryCaseRegistry(journal).verify_pinned_case()
    assert RecoveryCaseRegistry(journal).get(record["case_id"]) == record


def test_registry_case_cannot_be_implicitly_acknowledged_by_tampering(tmp_path, case_key):
    journal = FakeJournal(tmp_path)
    cases = RecoveryCaseRegistry(journal)
    case = cases.register_from_reconciled(observed_main_oid=MAIN)
    path = cases.root / (case["case_id"] + ".json")
    payload = path.read_text(encoding="utf-8")
    assert "PENDING_REVIEW" in payload
    path.write_text(payload.replace("PENDING_REVIEW", "ACKNOWLEDGED"), encoding="utf-8")
    with pytest.raises(RecoveryRequired, match="inauthentic"):
        cases.verify_pinned_case()


def test_legacy_clean_without_rv03_pin_retains_compatible_fast_path(tmp_path, case_key):
    journal = FakeJournal(tmp_path, status="CLEAN")
    assert "rv03_case_id" not in journal.document
    assert RecoveryCaseRegistry(journal).verify_pinned_case() is None
    assert RecoveryCaseRegistry(journal).list_cases() == []


def test_startup_rejects_untrusted_main_without_reset_or_publish(tmp_path, monkeypatch, case_key):
    from centermanager.database import mutation_authority
    from centermanager.platform import write_recovery
    from centermanager.platform.sync.startup_sync import StartupSynchronization

    journal = FakeJournal(tmp_path, status="OPEN")
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: journal)
    monkeypatch.setattr(mutation_authority, "gate_for",
                        lambda: SimpleNamespace(lock=RLock(), closed=True))
    writes = []

    def forbidden(*args, **kwargs):
        writes.append((args, kwargs))
        raise AssertionError("untrusted startup must never reset or publish")

    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: MAIN,
        observe_remote_main_commit=lambda: "f" * 40,
        get_local_main_commit=lambda: BASE,
        reset_to_remote=forbidden,
        publish_only=forbidden,
        release_lock=forbidden,
        renew_lock=forbidden,
    )
    startup = StartupSynchronization(provider)
    assert not startup._prepare_authoritative_startup_replacement()
    assert journal.inspect()["status"] == "OPEN"
    assert writes == []
    assert not (tmp_path / "cases").exists()


def test_old_unknown_publish_cannot_be_upgraded_to_verified_by_case_creation(tmp_path, case_key):
    journal = FakeJournal(tmp_path)
    journal.document["publication"] = "UNVERIFIED"
    journal.document["published_oid"] = MAIN  # remote equality alone is no acknowledgement
    case = RecoveryCaseRegistry(journal).register_from_reconciled(observed_main_oid=MAIN)
    assert case["publication"] == "UNVERIFIED"
    assert case["published_oid"] is None
    assert case["change_log_coverage"] == "UNKNOWN"
