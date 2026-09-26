from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.services.enrollment_transfer_service import (
    EnrollmentTransferService,
    EnrollmentTransferValidationError,
)


def _root() -> Path:
    return Path(__file__).resolve().parents[1]


def _existing_transfer(**overrides):
    values = {
        "source_enrollment_id": 10,
        "target_enrollment": SimpleNamespace(class_id=30),
        "transferred_credit": Decimal("250000.0000"),
        "reason": "Move class",
        "idempotency_key": "source-enrollment:10",
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_default_idempotency_key_is_stable_per_source_enrollment():
    assert EnrollmentTransferService._idempotency_key(10, None) == "source-enrollment:10"
    assert EnrollmentTransferService._idempotency_key(10, " retry-10 ") == "retry-10"


def test_idempotent_replay_requires_the_full_command_to_match():
    existing = _existing_transfer()
    command = dict(
        source_enrollment_id=10,
        target_class_id=30,
        transferred_credit=Decimal("250000.0000"),
        reason="Move class",
        idempotency_key="source-enrollment:10",
    )
    assert EnrollmentTransferService._same_command(existing, **command)

    changed = dict(command)
    changed["target_class_id"] = 31
    assert not EnrollmentTransferService._same_command(existing, **changed)

    changed = dict(command)
    changed["transferred_credit"] = Decimal("250001.0000")
    assert not EnrollmentTransferService._same_command(existing, **changed)


def test_same_source_different_command_is_a_deterministic_domain_conflict():
    service = EnrollmentTransferService.__new__(EnrollmentTransferService)
    repo = SimpleNamespace(
        get_by_idempotency_key=lambda _key: None,
        get_for_source=lambda _source_id: _existing_transfer(),
    )
    with pytest.raises(
        EnrollmentTransferValidationError,
        match="already completed a different transfer",
    ):
        service._existing_or_conflict(
            repo,
            source_enrollment_id=10,
            target_class_id=31,
            transferred_credit=Decimal("250000.0000"),
            reason="Move class",
            idempotency_key="source-enrollment:10",
        )


def test_migration_adds_source_idempotency_and_active_target_uniqueness():
    source = (
        _root() / "migrations/versions/1e10a038_transfer_concurrency_guards.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "1e10a038"' in source
    assert 'down_revision = "1e10a037"' in source
    assert '"idempotency_key"' in source
    assert '"uq_enrollment_transfer_source"' in source
    assert '"uq_enrollment_transfer_idempotency_key"' in source
    assert '"uq_enrollments_active_student_class"' in source
    assert "status = 'ACTIVE' AND class_id IS NOT NULL" in source


def test_repository_serializes_capacity_balance_and_duplicate_checks():
    source = (
        _root()
        / "src/centermanager/repositories/enrollment_transfer_repository.py"
    ).read_text(encoding="utf-8")

    assert "acquire_command_lock" in source
    assert 'dialect == "sqlite"' in source
    assert 'exec_driver_sql("BEGIN IMMEDIATE")' in source
    assert "with_for_update()" in source
    assert "get_by_idempotency_key" in source
    assert "get_for_source" in source
    assert "flush_guarded" in source
    assert "except IntegrityError" in source


def test_service_locks_before_check_then_act_and_rolls_back_uniqueness_races():
    source = (
        _root() / "src/centermanager/services/enrollment_transfer_service.py"
    ).read_text(encoding="utf-8")

    lock_at = source.index("transfer_repo.acquire_command_lock(")
    duplicate_at = source.index("enrollments.exists(source.student_id, target_class_id")
    capacity_at = source.index("enrollments.get_active_by_class(target_class_id)")
    balance_at = source.index("source_balance = self._source_balance(session, source)")
    assert lock_at < duplicate_at < capacity_at < balance_at

    assert "if not transfer_repo.flush_guarded():" in source
    assert "self._recover_conflict(" in source
    assert 'source.status = "WITHDRAWN"' in source
    assert "session.commit()" in source


def test_credit_consumption_is_checked_inside_the_serialized_transfer_transaction():
    source = (
        _root() / "src/centermanager/services/enrollment_transfer_service.py"
    ).read_text(encoding="utf-8")
    transfer_body = source.split("def transfer(", 1)[1]

    assert "acquire_command_lock" in transfer_body
    assert "source_balance = self._source_balance(session, source)" in transfer_body
    assert "available_credit = max(-source_balance" in transfer_body
    assert "credit > available_credit" in transfer_body
    assert transfer_body.index("acquire_command_lock") < transfer_body.index("credit > available_credit")


def test_active_enrollment_unique_index_is_present_in_orm_metadata():
    source = (
        _root() / "src/centermanager/models/enrollment.py"
    ).read_text(encoding="utf-8")
    assert '"uq_enrollments_active_student_class"' in source
    assert "unique=True" in source
    assert "sqlite_where=text(\"status = 'ACTIVE' AND class_id IS NOT NULL\")" in source
