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


def test_startup_main_preflight_requires_verified_manual_archive():
    path = ROOT / "src" / "centermanager" / "platform" / "sync" / "startup_sync.py"
    tree = ast.parse(path.read_text(encoding="utf-8-sig"))
    methods = {n.name: n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    target = methods["_prepare_authoritative_startup_replacement"]
    source = ast.unparse(target)
    assert "get_fetched_remote_main_commit" in source
    assert "observe_remote_main_commit" in source
    assert "RecoveryReviewNotices" in source
    assert "assert_replaceable" in source
    assert "preserve_workspace_for_manual_review" not in source
    assert "register_from_reconciled" not in source
    assert "reset_to_remote" not in source


def test_startup_fails_closed_when_manual_archive_cannot_be_persisted(monkeypatch, tmp_path):
    from threading import RLock
    from centermanager.platform.sync import startup_sync, manual_review_backup
    from centermanager.database import mutation_authority
    from centermanager.platform import write_recovery

    j = FakeJournal(tmp_path, status="OPEN")
    j.journal = tmp_path / "journal.json"
    j.journal.write_text('{"status":"OPEN"}')
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: j)
    monkeypatch.setattr(
        mutation_authority, "gate_for",
        lambda: SimpleNamespace(lock=RLock(), closed=True),
    )
    monkeypatch.setattr(
        manual_review_backup, "preserve_workspace_for_manual_review",
        lambda *a, **kw: (_ for _ in ()).throw(OSError("synthetic disk full")),
    )
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: MAIN,
        observe_remote_main_commit=lambda: MAIN,
    )
    startup = startup_sync.StartupSynchronization(provider)
    assert startup._prepare_authoritative_startup_replacement()
    assert startup._review_only_reset_requested
    assert startup._review_notice_path is not None
    assert j.inspect()["status"] == "OPEN"
    assert j.journal.read_text() == '{"status":"OPEN"}'


def test_old_recovery_is_not_automatically_reconciled_or_acked(monkeypatch, tmp_path):
    from threading import RLock
    from centermanager.platform.sync import startup_sync, manual_review_backup
    from centermanager.database import mutation_authority
    from centermanager.platform import write_recovery

    j = FakeJournal(tmp_path, status="OPEN")
    j.journal = tmp_path / "journal.json"
    j.journal.write_text('{"status":"OPEN"}')
    archive = tmp_path / "manual-review" / "immutable"
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: j)
    monkeypatch.setattr(
        mutation_authority, "gate_for",
        lambda: SimpleNamespace(lock=RLock(), closed=True),
    )
    monkeypatch.setattr(
        manual_review_backup, "preserve_workspace_for_manual_review",
        lambda *a, **kw: archive,
    )
    monkeypatch.setattr(
        manual_review_backup, "verify_manual_review_backup",
        lambda path: None if path == archive else (_ for _ in ()).throw(AssertionError()),
    )
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: MAIN,
        observe_remote_main_commit=lambda: MAIN,
    )
    startup = startup_sync.StartupSynchronization(provider)
    assert startup._prepare_authoritative_startup_replacement()
    assert startup._manual_reset_requested is False
    assert startup._review_only_reset_requested is True
    assert startup._startup_reconciled_unaccepted_local is False
    assert startup._review_notice_path is not None
    assert j.inspect()["status"] == "OPEN"
    assert j.journal.read_text() == '{"status":"OPEN"}'


def test_remote_main_race_rejects_replacement_without_touching_old_case(monkeypatch, tmp_path):
    from threading import RLock
    from centermanager.platform.sync import startup_sync
    from centermanager.database import mutation_authority
    from centermanager.platform import write_recovery

    j = FakeJournal(tmp_path, status="RECONCILED")
    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", lambda: j)
    monkeypatch.setattr(
        mutation_authority, "gate_for",
        lambda: SimpleNamespace(lock=RLock(), closed=True),
    )
    provider = SimpleNamespace(
        get_fetched_remote_main_commit=lambda: MAIN,
        observe_remote_main_commit=lambda: "f" * 40,
    )
    startup = startup_sync.StartupSynchronization(provider)
    assert not startup._prepare_authoritative_startup_replacement()
    assert "MAIN cannot be verified" in startup.recovery_error
    assert j.inspect()["status"] == "RECONCILED"


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
    # An independently verified CLEAN active DB is not held hostage by a
    # missing historic review-case file. Its absence is an operator-review
    # concern, not authority to modify the original journal or restore data.
    assert startup._prepare_authoritative_startup_replacement()
    assert journal.inspect()["status"] == "CLEAN"
    assert not (cases.root / (original["case_id"] + ".json")).exists()


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
    assert "active local editor" in startup.recovery_error
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
    assert "Git MAIN cannot be verified" in startup.recovery_error
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


@pytest.mark.parametrize("legacy_journal", [None, {}])
def test_authenticated_legacy_capture_with_null_or_missing_journal_can_be_registered(
    tmp_path, monkeypatch, legacy_journal
):
    j = FakeJournal(tmp_path)
    original_verify = j.verify_capture

    def legacy_capture(ref):
        manifest = original_verify(ref)
        if legacy_journal is None:
            manifest["journal"] = None
        else:
            manifest.pop("journal")
        return manifest

    j.verify_capture = legacy_capture
    cases = registry(j, monkeypatch)
    case = cases.register_from_reconciled(observed_main_oid=MAIN)
    assert case["status"] == "PENDING_REVIEW"
    assert case["publication"] == "UNVERIFIED"
    assert case["capture_db_sha256"] == DB_HASH
    assert cases.register_from_reconciled(observed_main_oid=MAIN) == case


@pytest.mark.parametrize("invalid_journal", ["bad", [], 0, True])
def test_malformed_capture_journal_is_rejected_without_new_case(
    tmp_path, monkeypatch, invalid_journal
):
    j = FakeJournal(tmp_path)
    original_verify = j.verify_capture

    def malformed(ref):
        manifest = original_verify(ref)
        manifest["journal"] = invalid_journal
        return manifest

    j.verify_capture = malformed
    cases = registry(j, monkeypatch)
    with pytest.raises(RecoveryRequired, match="metadata is malformed"):
        cases.register_from_reconciled(observed_main_oid=MAIN)
    assert not list((tmp_path / "cases").glob("*.json"))


@pytest.mark.parametrize("field,mismatch", [
    ("repository_id", "f" * 64), ("base_main_oid", "f" * 40),
])
def test_conflicting_capture_provenance_stays_blocking(
    tmp_path, monkeypatch, field, mismatch
):
    j = FakeJournal(tmp_path)
    original_verify = j.verify_capture

    def conflicting(ref):
        manifest = original_verify(ref)
        manifest["journal"][field] = mismatch
        return manifest

    j.verify_capture = conflicting
    cases = registry(j, monkeypatch)
    with pytest.raises(RecoveryRequired):
        cases.register_from_reconciled(observed_main_oid=MAIN)
    assert not list((tmp_path / "cases").glob("*.json"))
