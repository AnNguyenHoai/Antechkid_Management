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
