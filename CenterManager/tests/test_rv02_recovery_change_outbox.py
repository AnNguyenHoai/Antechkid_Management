"""RV-02 rollback, idempotency and protected mirror guarantees.

All tests use synthetic sqlite and synthetic keys, never a real runtime
SQLCipher database or actual Git remote.
"""
from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from centermanager.models.recovery_change_event import RecoveryChangeEvent
from centermanager.services.recovery_change_outbox import (
    RecoveryOutboxError, read_session_events, record_in_session,
)
from centermanager.platform.recovery_change_mirror import (
    decrypt_mirrored_event, mirror_committed_event,
)

BASE = "a" * 40
KEY = bytes(range(32))


@pytest.fixture
def engine():
    engine = create_engine("sqlite:///:memory:")
    RecoveryChangeEvent.__table__.create(bind=engine)
    yield engine
    engine.dispose()


def _event(session, *, event_id=None, arguments=None):
    return record_in_session(
        session,
        write_session_id="unit-session",
        base_main_oid=BASE,
        actor_id=7,
        module="finance",
        action="CREATE",
        entity_type="Income",
        entity_id=17,
        summary_code="INCOME_CREATED",
        summary_args=arguments or {"income_id": 17},
        event_id=event_id,
    )


def test_business_row_and_outbox_commit_together(engine):
    with Session(engine) as session:
        _event(session)
        session.commit()
    with Session(engine) as session:
        records = read_session_events(session, "unit-session")
        assert len(records) == 1
        assert records[0].base_main_oid == BASE
        assert json.loads(records[0].summary_args_json) == {"income_id": "17"}
        assert records[0].operation_id


def test_outbox_rollback_does_not_emit_applied_event(engine):
    with Session(engine) as session:
        _event(session)
        session.rollback()
    with Session(engine) as session:
        assert read_session_events(session, "unit-session") == []


def test_outbox_pk_rejects_duplicate_retry_event(engine):
    event_id = str(uuid.uuid4())
    with Session(engine) as session:
        _event(session, event_id=event_id)
        session.commit()
    with Session(engine) as session:
        _event(session, event_id=event_id)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
    with Session(engine) as session:
        assert len(read_session_events(session, "unit-session")) == 1


def test_unsafe_summary_arguments_rejected_before_insert(engine):
    with Session(engine) as session:
        for payload in ({"name": "Student Nguyen"}, {"password": "secret value"},
                        {"password_id": "sensitive-hash"},
                        {"raw": {"nested": "sensitive"}}, {"notes": "<html>"}):
            with pytest.raises(RecoveryOutboxError):
                _event(session, arguments=payload)
        session.rollback()
    with Session(engine) as session:
        assert read_session_events(session, "unit-session") == []


def test_encrypted_mirror_is_immutable_and_authentic(engine, tmp_path):
    with Session(engine) as session:
        item = _event(session)
        session.commit()
        session.refresh(item)
        path = mirror_committed_event(item, recovery_root=tmp_path, encryption_key=KEY)
        assert path.exists()
        assert "unit-session" in str(path)
        raw = path.read_bytes()
        assert b"Income" not in raw
        assert b"INCOME_CREATED" not in raw
        first = decrypt_mirrored_event(path, encryption_key=KEY)
        assert first["entity_id"] == "17"
        assert first["base_main_oid"] == BASE
        assert path == mirror_committed_event(item, recovery_root=tmp_path, encryption_key=KEY)
        assert path.read_bytes() == raw
        with pytest.raises(Exception):
            decrypt_mirrored_event(path, encryption_key=bytes(reversed(KEY)))
        path.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
        with pytest.raises(Exception):
            decrypt_mirrored_event(path, encryption_key=KEY)


def test_mirror_is_not_created_by_uncommitted_event(engine, tmp_path):
    with Session(engine) as session:
        _event(session)
        session.rollback()
    assert not list(tmp_path.rglob("*.enc"))


def test_invalid_ids_and_main_oid_rejected(engine):
    with Session(engine) as session:
        with pytest.raises(RecoveryOutboxError):
            record_in_session(session, write_session_id="", base_main_oid=BASE,
                              module="finance", action="CREATE", entity_type="Income")
        with pytest.raises(RecoveryOutboxError):
            record_in_session(session, write_session_id="s", base_main_oid="A+10",
                              module="finance", action="CREATE", entity_type="Income")


def test_verified_write_adapter_mirrors_only_after_successful_commit(engine, tmp_path, monkeypatch):
    from centermanager.services import recovery_change_outbox as recorder
    from centermanager.platform import write_recovery
    from centermanager.database.encryption import DatabaseKeyStore

    class SyntheticJournal:
        root = tmp_path

        def inspect(self):
            return {
                "status": "OPEN", "session_id": "unit-session",
                "base_main_oid": BASE, "mutation_authority_lost": False,
            }

    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", SyntheticJournal)
    monkeypatch.setattr(DatabaseKeyStore, "load", lambda self: KEY)
    engine._cm_runtime_owned = True
    with Session(engine) as session:
        item = recorder.record_for_active_write(
            session, module="student", action="CREATE",
            entity_type="Student", entity_id=77,
            summary_args={"student_id": 77},
        )
        assert item is not None
        assert not list(tmp_path.rglob("*.enc"))
        session.commit()
        recorder.mirror_after_successful_commit(session)
        from centermanager.platform.recovery_mirror_worker import drain_before_capture
        drain_before_capture(timeout_seconds=10.0)
        encrypted = list(tmp_path.rglob("*.enc"))
        assert len(encrypted) == 1
        payload = decrypt_mirrored_event(encrypted[0], encryption_key=KEY)
        assert payload["entity_id"] == "77"
    with Session(engine) as session:
        assert len(read_session_events(session, "unit-session")) == 1


def test_failed_external_mirror_does_not_rollback_committed_user_data(engine, tmp_path, monkeypatch):
    from centermanager.services import recovery_change_outbox as recorder
    from centermanager.platform import write_recovery
    from centermanager.database.encryption import DatabaseKeyStore

    class SyntheticJournal:
        root = tmp_path

        def inspect(self):
            return {
                "status": "OPEN", "session_id": "unit-session",
                "base_main_oid": BASE, "mutation_authority_lost": False,
            }

    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", SyntheticJournal)
    monkeypatch.setattr(DatabaseKeyStore, "load", lambda self: (_ for _ in ()).throw(OSError("unavailable")))
    engine._cm_runtime_owned = True
    with Session(engine) as session:
        recorder.record_for_active_write(
            session, module="finance", action="CREATE",
            entity_type="Income", entity_id=55,
            summary_args={"income_id": 55},
        )
        session.commit()
        recorder.mirror_after_successful_commit(session)  # must not raise
        from centermanager.platform.recovery_mirror_worker import drain_before_capture
        drain_before_capture(timeout_seconds=10.0)
    assert not list(tmp_path.rglob("*.enc"))
    with Session(engine) as session:
        assert len(read_session_events(session, "unit-session")) == 1


def test_missing_write_journal_emits_no_event_and_preserves_authority_boundary(engine, tmp_path, monkeypatch):
    """Ancillary outbox must not mask the existing SQLCipher mutation gate.

    These tests use an unguarded synthetic DB; real READ/stale authority denial
    remains covered by E1B-2B mutation-gate integration tests.
    """
    from centermanager.services import recovery_change_outbox as recorder
    from centermanager.platform import write_recovery

    class SyntheticJournal:
        root = tmp_path

        def inspect(self):
            return {"status": "RECOVERY_REQUIRED"}

    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", SyntheticJournal)
    engine._cm_runtime_owned = True
    with Session(engine) as session:
        assert recorder.record_for_active_write(
            session, module="student", action="UPDATE",
            entity_type="Student", entity_id=2,
        ) is None
        session.commit()
    with Session(engine) as session:
        assert read_session_events(session, "unit-session") == []


def test_signed_publication_receipt_requires_verified_main(tmp_path):
    from centermanager.platform.recovery_publication_receipt import (
        InvalidPublicationReceipt, read_verified_receipt, record_verified_publication,
    )
    document = {
        "status": "PUBLISHED", "publication": "VERIFIED",
        "session_id": "synthetic-session", "base_main_oid": "a" * 40,
        "published_oid": "b" * 40,
    }
    path = record_verified_publication(document, recovery_root=tmp_path, signing_key=KEY)
    receipt = read_verified_receipt(path, signing_key=KEY)
    assert receipt["base_main_oid"] == "a" * 40
    assert receipt["published_oid"] == "b" * 40
    assert record_verified_publication(document, recovery_root=tmp_path, signing_key=KEY) == path
    with pytest.raises(InvalidPublicationReceipt):
        record_verified_publication(
            {**document, "publication": "UNVERIFIED"}, recovery_root=tmp_path, signing_key=KEY
        )
    with pytest.raises(InvalidPublicationReceipt):
        record_verified_publication(
            {**document, "published_oid": "c" * 40}, recovery_root=tmp_path, signing_key=KEY
        )
    with pytest.raises(InvalidPublicationReceipt):
        read_verified_receipt(path, signing_key=bytes(reversed(KEY)))


def test_signed_receipt_detects_tampering(tmp_path):
    from centermanager.platform.recovery_publication_receipt import (
        InvalidPublicationReceipt, read_verified_receipt, record_verified_publication,
    )
    document = {
        "status": "PUBLISHED", "publication": "VERIFIED",
        "session_id": "unit-session", "base_main_oid": "a" * 40,
        "published_oid": "b" * 40,
    }
    path = record_verified_publication(document, recovery_root=tmp_path, signing_key=KEY)
    raw = json.loads(path.read_text(encoding="utf-8"))
    raw["published_oid"] = "c" * 40
    path.write_text(json.dumps(raw), encoding="utf-8")
    with pytest.raises(InvalidPublicationReceipt):
        read_verified_receipt(path, signing_key=KEY)


def test_real_sqlcipher_wal_commit_survives_missing_external_mirror(tmp_path):
    """Crash window: data and outbox committed; encrypted mirror not yet copied."""
    from sqlalchemy import text
    from sqlalchemy.pool import NullPool
    from centermanager.database.encryption import load_sqlcipher_driver, apply_sqlcipher_key

    database = tmp_path / "synthetic-center.db"
    cipher = load_sqlcipher_driver()

    def connect():
        conn = cipher.connect(str(database), check_same_thread=False)
        apply_sqlcipher_key(conn, KEY)
        return conn

    raw = connect()
    try:
        raw.execute("PRAGMA journal_mode=WAL")
        raw.execute("CREATE TABLE local_business (id INTEGER PRIMARY KEY, code TEXT NOT NULL)")
        raw.commit()
    finally:
        raw.close()

    encrypted_engine = create_engine("sqlite://", creator=connect, poolclass=NullPool)
    try:
        RecoveryChangeEvent.__table__.create(encrypted_engine)
        with Session(encrypted_engine) as session:
            session.execute(text("INSERT INTO local_business (code) VALUES ('COMMITTED')"))
            record_in_session(
                session, write_session_id="synthetic-sqlcipher", base_main_oid=BASE,
                module="student", action="CREATE", entity_type="Student", entity_id=1,
                summary_args={"student_id": 1},
            )
            session.commit()
        # Simulate process crash here: mirror_committed_event was NEVER called.
        with Session(encrypted_engine) as session:
            assert session.execute(text("SELECT COUNT(*) FROM local_business")).scalar_one() == 1
            assert len(read_session_events(session, "synthetic-sqlcipher")) == 1
        assert not list(tmp_path.rglob("*.enc"))

        # Both business row and outbox must be committed or both absent.
        with Session(encrypted_engine) as session:
            session.execute(text("INSERT INTO local_business (code) VALUES ('ROLLED_BACK')"))
            record_in_session(
                session, write_session_id="synthetic-sqlcipher", base_main_oid=BASE,
                module="student", action="CREATE", entity_type="Student", entity_id=2,
                summary_args={"student_id": 2},
            )
            session.rollback()
        with Session(encrypted_engine) as session:
            assert session.execute(text("SELECT COUNT(*) FROM local_business")).scalar_one() == 1
            assert len(read_session_events(session, "synthetic-sqlcipher")) == 1
    finally:
        encrypted_engine.dispose()


def test_mirror_coverage_is_unknown_without_attested_sqlcipher_source(engine, tmp_path):
    from centermanager.platform.recovery_change_mirror import assess_mirror_coverage
    with Session(engine) as session:
        _event(session)
        session.commit()
        events = read_session_events(session, "unit-session")
        assert assess_mirror_coverage(
            events, recovery_root=tmp_path, encryption_key=KEY,
            committed_source_attested=False,
        )["status"] == "UNKNOWN"
        missing = assess_mirror_coverage(
            events, recovery_root=tmp_path, encryption_key=KEY,
            committed_source_attested=True,
        )
        assert missing["status"] == "INCOMPLETE"
        assert missing["verified"] == 0
        for event in events:
            mirror_committed_event(event, recovery_root=tmp_path, encryption_key=KEY)
        complete = assess_mirror_coverage(
            events, recovery_root=tmp_path, encryption_key=KEY,
            committed_source_attested=True,
        )
        assert complete == {"status": "COMPLETE", "expected": 1, "verified": 1}


def test_admin_reset_cannot_delete_recovery_outbox_history():
    from centermanager.repositories.admin_data_reset_repository import AdminDataResetRepository
    from centermanager.database.base import Base

    assert "recovery_change_outbox" in Base.metadata.tables
    assert "recovery_change_outbox" in AdminDataResetRepository.PROTECTED_TABLES
    assert "recovery_change_outbox" not in AdminDataResetRepository.BUSINESS_TABLES


def test_rolled_back_session_info_does_not_fabricate_mirror_after_later_commit(
    engine, tmp_path, monkeypatch
):
    from centermanager.services import recovery_change_outbox as recorder
    from centermanager.platform import write_recovery
    from centermanager.database.encryption import DatabaseKeyStore

    class SyntheticJournal:
        root = tmp_path

        def inspect(self):
            return {
                "status": "OPEN", "session_id": "unit-session",
                "base_main_oid": BASE, "mutation_authority_lost": False,
            }

    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", SyntheticJournal)
    monkeypatch.setattr(DatabaseKeyStore, "load", lambda self: KEY)
    engine._cm_runtime_owned = True
    with Session(engine) as session:
        rolled_back = recorder.record_for_active_write(
            session, module="student", action="CREATE",
            entity_type="Student", entity_id=61, summary_args={"student_id": 61},
        )
        session.rollback()  # session.info still retains the Python reference
        accepted = recorder.record_for_active_write(
            session, module="student", action="CREATE",
            entity_type="Student", entity_id=62, summary_args={"student_id": 62},
        )
        session.commit()
        recorder.mirror_after_successful_commit(session)
        from centermanager.platform.recovery_mirror_worker import drain_before_capture
        drain_before_capture(timeout_seconds=10.0)
    files = list(tmp_path.rglob("*.enc"))
    assert len(files) == 1
    assert files[0].stem == accepted.event_id
    assert files[0].stem != rolled_back.event_id
    with Session(engine) as session:
        events = read_session_events(session, "unit-session")
        assert [event.entity_id for event in events] == ["62"]


def test_mocked_session_cannot_impersonate_protected_runtime():
    """MagicMock bind attributes are truthy even when no real Engine exists."""
    from unittest.mock import MagicMock
    from centermanager.services.recovery_change_outbox import record_for_active_write

    session = MagicMock()
    session.get_bind.return_value._cm_runtime_owned = True
    result = record_for_active_write(
        session,
        module="work_registration",
        action="REOPEN",
        entity_type="EmployeeWorkRegistration",
        entity_id=None,
        summary_args={"employee_id": 7},
    )
    assert result is None
    session.add.assert_not_called()
    session.flush.assert_not_called()
