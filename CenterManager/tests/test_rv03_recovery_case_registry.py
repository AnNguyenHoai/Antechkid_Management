"""RV-03 Recovery Case persistence, retry and fail-closed integration contracts.

Synthetic journal tests never interact with live Git refs or production SQLCipher.
Startup tests verify that preflight cannot install MAIN before case persistence.
"""
from __future__ import annotations

import ast
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.platform.recovery_case_registry import RecoveryCaseRegistry
from centermanager.platform.write_recovery import RecoveryRequired

ROOT = Path(__file__).resolve().parents[1]
BASE = "a" * 40
MAIN = "b" * 40
DB_HASH = "c" * 64


class FakeJournal:
    def __init__(self, root, *, status="RECONCILED", publish="UNVERIFIED"):
        self.root = root
        self.capture = root / "captures" / "synthetic"
        self.capture.mkdir(parents=True)
        self.document = {
            "status": status, "base_main_oid": BASE,
            "accepted_main_oid": MAIN,
            "repository_id": "e" * 64,
            "session_id": "session-001",
            "last_capture": str(self.capture),
            "publication": publish,
            "published_oid": MAIN if publish == "VERIFIED" else None,
        }
        self.capture_valid = True

    def inspect(self):
        return dict(self.document)

    def update(self, **fields):
        self.document.update(fields)

    def verify_capture(self, ref):
        if not self.capture_valid or Path(ref).resolve() != self.capture.resolve():
            raise RecoveryRequired("Synthetic capture verification failed")
        return {
            "files": {"center.db": DB_HASH, "attachments/document.dat": "d" * 64},
            "journal": {"base_main_oid": BASE},
        }


def registry(journal, monkeypatch):
    # Synthetic stable key; real production registry loads protected DPAPI key.
    monkeypatch.setattr(RecoveryCaseRegistry, "_key", lambda self: bytes(range(32)))
    return RecoveryCaseRegistry(journal)


def test_unaccepted_case_is_saved_once_and_survives_restart(tmp_path, monkeypatch):
    j = FakeJournal(tmp_path)
    cases = registry(j, monkeypatch)
    first = cases.register_from_reconciled(observed_main_oid=MAIN)
    assert first["status"] == "PENDING_REVIEW"
    assert first["change_log_coverage"] == "UNKNOWN"
    assert first["publication"] == "UNVERIFIED"
    assert first["capture_db_sha256"] == DB_HASH
    assert len(list((tmp_path / "cases").glob("*.json"))) == 1
    assert cases.register_from_reconciled(observed_main_oid=MAIN) == first
    assert RecoveryCaseRegistry(j).list_cases() == [first]


def test_case_not_labeled_missing_remote_when_publication_unknown(tmp_path, monkeypatch):
    j = FakeJournal(tmp_path)
    j.document["published_oid"] = MAIN
    case = registry(j, monkeypatch).register_from_reconciled(observed_main_oid=MAIN)
    assert case["publication"] == "UNVERIFIED"
    assert case["published_oid"] is None


def test_verified_publication_requires_explicit_provenance(tmp_path, monkeypatch):
    j = FakeJournal(tmp_path, publish="VERIFIED")
    case = registry(j, monkeypatch).register_from_reconciled(observed_main_oid=MAIN)
    assert case["publication"] == "VERIFIED"
    assert case["published_oid"] == MAIN


@pytest.mark.parametrize("failure", ["not_reconciled", "wrong_main", "broken_capture"])
def test_registry_fails_closed_before_replace(tmp_path, monkeypatch, failure):
    j = FakeJournal(tmp_path)
    if failure == "not_reconciled":
        j.document["status"] = "OPEN"
    if failure == "broken_capture":
        j.capture_valid = False
    cases = registry(j, monkeypatch)
    with pytest.raises(RecoveryRequired):
        cases.register_from_reconciled(
            observed_main_oid=("f" * 40) if failure == "wrong_main" else MAIN
        )
    assert not list((tmp_path / "cases").glob("*.json"))


def test_registry_tampering_blocks_recovery(tmp_path, monkeypatch):
    j = FakeJournal(tmp_path)
    cases = registry(j, monkeypatch)
    saved = cases.register_from_reconciled(observed_main_oid=MAIN)
    path = cases.root / (saved["case_id"] + ".json")
    raw = path.read_text(encoding="utf-8").replace("PENDING_REVIEW", "ACKNOWLEDGED")
    path.write_text(raw, encoding="utf-8")
    with pytest.raises(RecoveryRequired, match="inauthentic"):
        cases.get(saved["case_id"])
    with pytest.raises(RecoveryRequired):
        cases.register_from_reconciled(observed_main_oid=MAIN)


def test_existing_case_requires_original_capture_still_verified(tmp_path, monkeypatch):
    j = FakeJournal(tmp_path)
    cases = registry(j, monkeypatch)
    cases.register_from_reconciled(observed_main_oid=MAIN)
    j.capture_valid = False
    with pytest.raises(RecoveryRequired):
        cases.register_from_reconciled(observed_main_oid=MAIN)


def test_startup_preflight_enforces_case_before_reset():
    path = ROOT / "src" / "centermanager" / "platform" / "sync" / "startup_sync.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    methods = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    target = methods["_prepare_authoritative_startup_replacement"]
    calls = [
        (ast.unparse(c.func), c.lineno)
        for c in ast.walk(target) if isinstance(c, ast.Call)
    ]
    assert any(fn == "journal.reconcile" for fn, _ in calls)
    assert sum(fn.endswith(".register_from_reconciled") for fn, _ in calls) == 2
    pos_reconcile = min(n for fn, n in calls if fn == "journal.reconcile")
    pos_case = max(n for fn, n in calls if fn.endswith(".register_from_reconciled"))
    assert pos_reconcile < pos_case
    assert "reset_to_remote" not in ast.unparse(target)


def test_startup_refuses_to_replace_when_case_persistence_fails(monkeypatch, tmp_path):
    """A verified local capture without durable case must BLOCK MAIN installation."""
    from types import SimpleNamespace
    from threading import RLock
    from centermanager.platform.sync import startup_sync
    from centermanager.database import mutation_authority
    from centermanager.platform import write_recovery

    j = FakeJournal(tmp_path, status="OPEN")
    j.document["status"] = "OPEN"

    def denied_until_reconciled(*, legacy=False):
        if j.document["status"] != "RECONCILED":
            raise RecoveryRequired("local unaccepted changes")
        return None

    def reconcile(*, base_oid, accepted_main, observe_main):
        assert base_oid == BASE and accepted_main == MAIN
        assert observe_main() == MAIN
        j.document["status"] = "RECONCILED"

    j.assert_replaceable = denied_until_reconciled
    j.reconcile = reconcile
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: j)
    monkeypatch.setattr(mutation_authority, "gate_for",
                        lambda: SimpleNamespace(lock=RLock(), closed=True))

    original_register = RecoveryCaseRegistry.register_from_reconciled

    def disk_error(*args, **kwargs):
        raise OSError("synthetic recovery case disk unavailable")

    monkeypatch.setattr(RecoveryCaseRegistry, "register_from_reconciled", disk_error)
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: MAIN,
        observe_remote_main_commit=lambda: MAIN,
        get_local_main_commit=lambda: BASE,
    )
    startup = startup_sync.StartupSynchronization(provider)
    assert startup._prepare_authoritative_startup_replacement() is False
    assert j.document["status"] == "RECONCILED"
    assert startup._startup_reconciled_unaccepted_local is False

    # Even though journal.reconcile already succeeded, a retry must not
    # silently bypass a missing case when journal.status is RECONCILED.
    assert startup._prepare_authoritative_startup_replacement() is False
    monkeypatch.setattr(RecoveryCaseRegistry, "register_from_reconciled", original_register)


def test_startup_creates_recovery_case_and_reuses_it_after_interruption(monkeypatch, tmp_path):
    from types import SimpleNamespace
    from threading import RLock
    from centermanager.platform.sync import startup_sync
    from centermanager.database import mutation_authority
    from centermanager.platform import write_recovery

    j = FakeJournal(tmp_path, status="OPEN")
    j.document["status"] = "OPEN"
    j.assert_replaceable = lambda *, legacy=False: (
        None if j.document["status"] == "RECONCILED"
        else (_ for _ in ()).throw(RecoveryRequired("unaccepted"))
    )

    def reconcile(*, base_oid, accepted_main, observe_main):
        assert observe_main() == MAIN
        j.document["status"] = "RECONCILED"

    j.reconcile = reconcile
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: j)
    monkeypatch.setattr(mutation_authority, "gate_for",
                        lambda: SimpleNamespace(lock=RLock(), closed=True))
    monkeypatch.setattr(RecoveryCaseRegistry, "_key", lambda self: bytes(range(32)))
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: MAIN,
        observe_remote_main_commit=lambda: MAIN,
        get_local_main_commit=lambda: BASE,
    )

    startup = startup_sync.StartupSynchronization(provider)
    assert startup._prepare_authoritative_startup_replacement()
    assert j.document["status"] == "RECONCILED"
    assert len(RecoveryCaseRegistry(j).list_cases()) == 1

    # Simulate a crash after the case is durable but before Git reset; the
    # next process must recognize the existing case, not duplicate or erase.
    rebooted = startup_sync.StartupSynchronization(provider)
    assert rebooted._prepare_authoritative_startup_replacement()
    assert len(RecoveryCaseRegistry(j).list_cases()) == 1


def test_reconciled_case_rejects_main_advance_before_install(monkeypatch, tmp_path):
    """A previously approved MAIN cannot authorize a different later OID."""
    from threading import RLock
    from centermanager.platform.sync import startup_sync
    from centermanager.database import mutation_authority
    from centermanager.platform import write_recovery

    journal = FakeJournal(tmp_path, status="RECONCILED")
    journal.assert_replaceable = lambda *, legacy=False: None
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: journal)
    monkeypatch.setattr(mutation_authority, "gate_for",
                        lambda: SimpleNamespace(lock=RLock(), closed=True))
    monkeypatch.setattr(RecoveryCaseRegistry, "_key", lambda self: bytes(range(32)))
    cases = RecoveryCaseRegistry(journal)
    first = cases.register_from_reconciled(observed_main_oid=MAIN)
    remote_advanced = "f" * 40
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: remote_advanced,
        observe_remote_main_commit=lambda: remote_advanced,
        get_local_main_commit=lambda: BASE,
    )
    startup = startup_sync.StartupSynchronization(provider)
    assert startup._prepare_authoritative_startup_replacement() is False
    assert "Remote MAIN changed" in startup.recovery_error
    assert cases.list_cases() == [first]
    assert journal.inspect()["status"] == "RECONCILED"


def test_case_survives_clean_restart_without_automatic_acknowledgement(tmp_path, monkeypatch):
    j = FakeJournal(tmp_path)
    cases = registry(j, monkeypatch)
    old = cases.register_from_reconciled(observed_main_oid=MAIN)
    j.document.update(status="CLEAN", publication="VERIFIED")
    for _ in range(3):
        assert RecoveryCaseRegistry(j).list_cases() == [old]
        assert RecoveryCaseRegistry(j).get(old["case_id"])["status"] == "PENDING_REVIEW"


def test_missing_original_capture_fails_closed_on_case_reuse(tmp_path, monkeypatch):
    j = FakeJournal(tmp_path)
    cases = registry(j, monkeypatch)
    first = cases.register_from_reconciled(observed_main_oid=MAIN)
    # Even if the current journal still points to a valid capture ID, loss
    # of the original immutable captured proof is a release blocker.
    j.capture_valid = False
    with pytest.raises(RecoveryRequired):
        cases.register_from_reconciled(observed_main_oid=MAIN)
    assert cases.get(first["case_id"]) == first


def test_registry_requires_protected_key_when_encryption_is_required(tmp_path, monkeypatch):
    from centermanager.database import encryption
    j = FakeJournal(tmp_path)
    monkeypatch.setattr(encryption, "database_encryption_required", lambda: True)
    monkeypatch.setattr(
        encryption.DatabaseKeyStore, "load",
        lambda self: (_ for _ in ()).throw(encryption.DatabaseKeyUnavailable("missing DPAPI key")),
    )
    with pytest.raises(encryption.DatabaseKeyUnavailable):
        RecoveryCaseRegistry(j).register_from_reconciled(observed_main_oid=MAIN)
    assert not list((tmp_path / "cases").glob("*.json"))


def test_pinned_case_missing_after_clean_restart_is_blocking(tmp_path, monkeypatch):
    j = FakeJournal(tmp_path)
    cases = registry(j, monkeypatch)
    entry = cases.register_from_reconciled(observed_main_oid=MAIN)
    assert j.inspect()["rv03_case_id"] == entry["case_id"]
    j.document["status"] = "CLEAN"
    cases.verify_pinned_case()
    (cases.root / (entry["case_id"] + ".json")).unlink()
    with pytest.raises(RecoveryRequired, match="removed"):
        cases.verify_pinned_case()


def test_pinned_case_capture_corruption_blocks_clean_restart(tmp_path, monkeypatch):
    j = FakeJournal(tmp_path)
    cases = registry(j, monkeypatch)
    cases.register_from_reconciled(observed_main_oid=MAIN)
    j.document["status"] = "CLEAN"
    j.capture_valid = False
    with pytest.raises(RecoveryRequired):
        RecoveryCaseRegistry(j).verify_pinned_case()


def test_startup_clean_state_rejects_missing_pinned_case(monkeypatch, tmp_path):
    from threading import RLock
    from centermanager.platform.sync import startup_sync
    from centermanager.database import mutation_authority
    from centermanager.platform import write_recovery

    journal = FakeJournal(tmp_path)
    cases = registry(journal, monkeypatch)
    original = cases.register_from_reconciled(observed_main_oid=MAIN)
    journal.document["status"] = "CLEAN"
    journal.assert_replaceable = lambda *, legacy=False: None
    (cases.root / (original["case_id"] + ".json")).unlink()
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: journal)
    monkeypatch.setattr(
        mutation_authority, "gate_for",
        lambda: SimpleNamespace(lock=RLock(), closed=True)
    )
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: MAIN,
        observe_remote_main_commit=lambda: MAIN,
        get_local_main_commit=lambda: MAIN,
    )
    startup = startup_sync.StartupSynchronization(provider)
    assert not startup._prepare_authoritative_startup_replacement()
    assert "removed" in startup.recovery_error
    assert journal.inspect()["status"] == "CLEAN"


def test_startup_with_active_local_writer_never_creates_case_or_reconciles(monkeypatch, tmp_path):
    """An old live WRITE authority cannot be crossed by MAIN installation."""
    from threading import RLock
    from centermanager.platform.sync import startup_sync
    from centermanager.database import mutation_authority
    from centermanager.platform import write_recovery

    j = FakeJournal(tmp_path, status="OPEN")
    j.assert_replaceable = lambda *, legacy=False: (
        (_ for _ in ()).throw(AssertionError("writer must block before journal access"))
    )
    j.reconcile = lambda **kwargs: (
        (_ for _ in ()).throw(AssertionError("active owner cannot reconcile"))
    )
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: j)
    monkeypatch.setattr(mutation_authority, "gate_for",
                        lambda: SimpleNamespace(lock=RLock(), closed=False))
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: MAIN,
        observe_remote_main_commit=lambda: MAIN,
        get_local_main_commit=lambda: BASE,
    )
    startup = startup_sync.StartupSynchronization(provider)
    assert startup._prepare_authoritative_startup_replacement() is False
    assert "local WRITE editor" in startup.recovery_error
    assert not list((tmp_path / "cases").glob("*.json"))


def test_unverified_remote_main_never_reconciles_or_creates_case(monkeypatch, tmp_path):
    """A fetched OID without matching independent observation is no authority."""
    from threading import RLock
    from centermanager.platform.sync import startup_sync
    from centermanager.database import mutation_authority
    from centermanager.platform import write_recovery

    j = FakeJournal(tmp_path, status="OPEN")
    j.reconcile = lambda **kwargs: (
        (_ for _ in ()).throw(AssertionError("unknown MAIN cannot reconcile"))
    )
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: j)
    monkeypatch.setattr(mutation_authority, "gate_for",
                        lambda: SimpleNamespace(lock=RLock(), closed=True))
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: MAIN,
        observe_remote_main_commit=lambda: "f" * 40,
        get_local_main_commit=lambda: BASE,
    )
    startup = startup_sync.StartupSynchronization(provider)
    assert startup._prepare_authoritative_startup_replacement() is False
    assert "independently verified" in startup.recovery_error
    assert j.inspect()["status"] == "OPEN"
    assert not list((tmp_path / "cases").glob("*.json"))


def test_interrupted_case_journal_pin_is_recovered_without_duplicate(tmp_path, monkeypatch):
    """Crash between durable case file and journal pin must be retryable."""
    j = FakeJournal(tmp_path)
    cases = registry(j, monkeypatch)
    original_update = j.update
    attempts = {"count": 0}

    def interrupted_update(**fields):
        attempts["count"] += 1
        if attempts["count"] == 1:
            raise OSError("simulated crash during journal pin")
        return original_update(**fields)

    j.update = interrupted_update
    with pytest.raises(OSError, match="simulated crash"):
        cases.register_from_reconciled(observed_main_oid=MAIN)
    saved = list((tmp_path / "cases").glob("*.json"))
    assert len(saved) == 1
    assert "rv03_case_id" not in j.inspect()
    recovered = RecoveryCaseRegistry(j).register_from_reconciled(observed_main_oid=MAIN)
    assert recovered["case_id"] == saved[0].stem
    assert j.inspect()["rv03_case_id"] == recovered["case_id"]
    assert len(list((tmp_path / "cases").glob("*.json"))) == 1
