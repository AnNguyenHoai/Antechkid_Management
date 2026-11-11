"""RV-02 immutable recovery operation index (not a database replay log).

No filesystem or network I/O occurs on this business transaction path. A
committed event and the user mutation share the caller's SQLCipher transaction;
both roll back together. A later mirror process copies *committed* events to
an encrypted file outside replaceable runtime.
"""
from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Mapping

from sqlalchemy.orm import Session

from centermanager.models.recovery_change_event import RecoveryChangeEvent

_SAFE_KEY = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$")
_SAFE_VALUE = re.compile(r"^[a-zA-Z0-9_.:-]{0,100}$")
# Exact allowlist: a *_id suffix alone could accidentally expose secrets.
_SAFE_SUMMARY_KEYS = frozenset({
    "income_id", "expense_id", "student_id", "session_id", "class_id",
    "finance_period_id", "tuition_adjustment_id", "enrollment_id",
    "teacher_id", "assessment_id", "parent_id", "note_id",
    "highlight_id", "employee_id", "user_id", "role_id",
    "schedule_week_id", "registration_period_id", "registration_id",
    "transfer_id", "source_enrollment_id", "attachment_id",
    "settlement_id", "record_count", "changed_count",
})


class RecoveryOutboxError(ValueError):
    """Invalid event or missing explicit collaboration provenance."""


def _safe_summary_args(arguments: Mapping[str, object] | None) -> str:
    """Allow only identifiers/tags, never a user's free-form notes or passwords."""
    fields: dict[str, str] = {}
    for key, value in (arguments or {}).items():
        if not isinstance(key, str) or key not in _SAFE_SUMMARY_KEYS:
            raise RecoveryOutboxError("Recovery summary only permits approved IDs and counts")
        if not isinstance(value, (str, int, bool)):
            raise RecoveryOutboxError("Recovery summary arguments must be scalar identifiers")
        item = str(value)
        if not _SAFE_VALUE.fullmatch(item):
            raise RecoveryOutboxError("Recovery summary contains unapproved free-form data")
        fields[key] = item
    if len(fields) > 16:
        raise RecoveryOutboxError("Recovery summary may contain at most 16 identifiers")
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def record_in_session(
    session: Session,
    *,
    write_session_id: str,
    base_main_oid: str,
    module: str,
    action: str,
    entity_type: str,
    entity_id: str | int | None = None,
    actor_id: str | int | None = None,
    summary_code: str | None = None,
    summary_args: Mapping[str, object] | None = None,
    operation_id: str | None = None,
    event_id: str | None = None,
) -> RecoveryChangeEvent:
    """Attach an immutable operation to the caller's *uncommitted* DB session.

    This method must NOT commit, flush or open another SQLCipher connection.
    A caller is responsible for verifying WRITE authority and ensuring that
    the event is added only for a real change. The event ID can be supplied by
    a retrying caller to enforce exact idempotency at the database PK.
    """
    if (not isinstance(write_session_id, str) or write_session_id in {".", ".."}
            or not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", write_session_id)):
        raise RecoveryOutboxError("Verified safe WRITE session identifier is required")
    if not re.fullmatch(r"[0-9a-fA-F]{40,64}", base_main_oid or ""):
        raise RecoveryOutboxError("Full verified base MAIN OID is required")
    for field, value, maximum in (
        ("module", module, 60),
        ("action", action, 60),
        ("entity_type", entity_type, 80),
    ):
        if not isinstance(value, str) or not _SAFE_KEY.fullmatch(value) or len(value) > maximum:
            raise RecoveryOutboxError("Invalid recovery " + field)
    code = summary_code or (module + "_" + action)
    if not _SAFE_KEY.fullmatch(code) or len(code) > 120:
        raise RecoveryOutboxError("Invalid summary code")
    if entity_id is not None and (len(str(entity_id)) > 100 or not _SAFE_VALUE.fullmatch(str(entity_id))):
        raise RecoveryOutboxError("Invalid entity identifier")
    if actor_id is not None and (len(str(actor_id)) > 100 or not _SAFE_VALUE.fullmatch(str(actor_id))):
        raise RecoveryOutboxError("Invalid actor identifier")
    op = operation_id or str(uuid.uuid4())
    eid = event_id or str(uuid.uuid4())
    for value in (op, eid):
        try:
            uuid.UUID(value)
        except (ValueError, TypeError, AttributeError) as exc:
            raise RecoveryOutboxError("Operation and event IDs must be UUIDs") from exc
    event = RecoveryChangeEvent(
        event_id=eid,
        operation_id=op,
        occurred_at_utc=datetime.now(timezone.utc).replace(tzinfo=None),
        write_session_id=write_session_id,
        base_main_oid=base_main_oid.lower(),
        actor_id=str(actor_id) if actor_id is not None else None,
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        summary_code=code,
        summary_args_json=_safe_summary_args(summary_args),
        schema_version=1,
    )
    session.add(event)
    return event


def read_session_events(session: Session, write_session_id: str) -> list[RecoveryChangeEvent]:
    """Read only committed events; caller must hold a valid read-only context."""
    return (
        session.query(RecoveryChangeEvent)
        .filter(RecoveryChangeEvent.write_session_id == write_session_id)
        .order_by(RecoveryChangeEvent.occurred_at_utc, RecoveryChangeEvent.event_id)
        .all()
    )


def record_for_active_write(
    session: Session,
    *,
    module: str,
    action: str,
    entity_type: str,
    entity_id: str | int | None,
    entity_object: object | None = None,
    summary_args: Mapping[str, object] | None = None,
    operation_id: str | None = None,
) -> RecoveryChangeEvent | None:
    """Production adapter: only a real protected WRITE runtime creates outbox data.

    Synthetic/unprotected test engines remain unchanged. This is *not* an
    authorization bypass; SQLCipher MutationAuthorityGate still controls all
    DML and commits. An active OPEN journal is required on protected runtime.
    """
    # Fake sessions and non-authoritative engines need no recovery outbox.
    # Service callers do not access persistence internals (EP-ARCH gates).
    get_bind = getattr(session, "get_bind", None)
    if not callable(get_bind):
        return None
    bind = get_bind()
    # MagicMock dynamically fabricates arbitrary attributes and converts
    # them to True, including _cm_runtime_owned. Require an actual SQLAlchemy
    # engine/connection before evaluating the production runtime marker.
    # This does NOT weaken the DB mutation gate: real SQLCipher engines still
    # enforce it independently at the SQL/commit boundary.
    from sqlalchemy.engine import Connection, Engine
    if not isinstance(bind, (Engine, Connection)):
        return None
    runtime_engine = bind.engine if isinstance(bind, Connection) else bind
    if getattr(runtime_engine, "_cm_runtime_owned", False) is not True:
        return None

    from centermanager.platform.write_recovery import WriteRecoveryJournal
    from centermanager.core.current_user import get_current_user
    try:
        journal = WriteRecoveryJournal()
        doc = journal.inspect()
    except Exception:
        # Old/corrupt/unwritable Recovery metadata must never veto business
        # DML. The independent SQLCipher mutation gate already authenticates
        # remote WRITE and domain permissions; omit only ancillary outbox data.
        import logging
        logging.getLogger(__name__).exception(
            "Recovery change log unavailable; business transaction continues "
            "under independent WRITE authority"
        )
        return None
    if (not doc or doc.get("status") != "OPEN"
            or doc.get("mutation_authority_lost")
            or not doc.get("session_id") or not doc.get("base_main_oid")):
        # Outbox is an ancillary record, not an authorization gate.
        # In READ/WAITING, lost authority, post-publish callbacks, maintenance,
        # and standalone service tests, the existing SQLCipher mutation gate
        # remains responsible for denying unauthorized writes at flush/commit.
        # Do not mask its MutationAuthorityError with an outbox-specific one.
        # No event is emitted when there is no verified active WRITE session.
        return None
    if entity_id is None and entity_object is not None:
        # Generated integer PK can only be known after the caller's pending
        # INSERT is flushed. This happens inside the same SQLCipher transaction.
        session.flush()
        entity_id = getattr(entity_object, "id", None)
    if entity_id is None:
        raise RecoveryOutboxError("Committed recovery operation needs a stable entity ID")
    normalized_args = dict(summary_args or {})
    for key, value in list(normalized_args.items()):
        if value is None and key.lower() in {
            "student_id", "income_id", "expense_id", "enrollment_id",
            "class_id", "session_id", "finance_period_id", "teacher_id",
            "assessment_id", "parent_id", "note_id", "highlight_id", "employee_id", "user_id", "role_id", "schedule_week_id", "registration_period_id",
        }:
            normalized_args[key] = entity_id
    actor = get_current_user()
    event = record_in_session(
        session,
        write_session_id=str(doc["session_id"]),
        base_main_oid=str(doc["base_main_oid"]),
        actor_id=getattr(actor, "id", None),
        module=module,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        summary_args=normalized_args,
        operation_id=operation_id,
    )
    session.info.setdefault("_rv02_after_commit_events", []).append(event)
    session.info["_rv02_recovery_root"] = journal.root
    return event


def mirror_after_successful_commit(session: Session) -> None:
    """Queue committed operation metadata; never block Save on crypto/fsync.

    Read each event from the committed transaction before enqueueing. Stale
    session.info references from rolled-back transactions are ignored. The
    background worker receives immutable bytes only and cannot mutate SQLCipher
    or Git MAIN. Queue overflow/failure means INCOMPLETE external mirror; the
    existing WAL-complete protected recovery capture remains authoritative.
    """
    import logging

    logger = logging.getLogger(__name__)
    info = getattr(session, "info", None)
    if not isinstance(info, dict):
        return
    pending = info.pop("_rv02_after_commit_events", [])
    root = info.pop("_rv02_recovery_root", None)
    if not pending or root is None:
        return
    try:
        from centermanager.platform.recovery_change_mirror import _payload
        from centermanager.platform.recovery_mirror_worker import submit_committed_payload

        for queued_event in pending:
            # Never mirror a rolled-back row retained in Python session.info
            # after another transaction later commits.
            committed = session.get(RecoveryChangeEvent, queued_event.event_id)
            if committed is None:
                continue
            if not submit_committed_payload(
                recovery_root=root, payload=_payload(committed),
                session_id=committed.write_session_id
            ):
                logger.error(
                    "RV-02 committed operation was not queued for mirror; "
                    "treat this recovery mirror as INCOMPLETE"
                )
    except Exception:
        logger.exception(
            "RV-02 committed outbox handoff failed; verified SQLCipher recovery "
            "capture is required; never treat the mirror as complete"
        )
