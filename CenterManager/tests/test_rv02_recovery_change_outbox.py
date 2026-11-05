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
    assert not list(tmp_path.rglob("*.enc"))
    with Session(engine) as session:
        assert len(read_session_events(session, "unit-session")) == 1


def test_missing_write_journal_fails_closed_on_protected_runtime(engine, tmp_path, monkeypatch):
    from centermanager.services import recovery_change_outbox as recorder
    from centermanager.platform import write_recovery

    class SyntheticJournal:
        root = tmp_path

        def inspect(self):
            return {"status": "RECOVERY_REQUIRED"}

    monkeypatch.setattr(write_recovery, "WriteRecoveryJournal", SyntheticJournal)
    engine._cm_runtime_owned = True
    with Session(engine) as session:
        with pytest.raises(RecoveryOutboxError):
            recorder.record_for_active_write(
                session, module="student", action="UPDATE",
                entity_type="Student", entity_id=2,
            )
        session.rollback()


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
