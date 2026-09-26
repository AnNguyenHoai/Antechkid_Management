# -*- coding: utf-8 -*-
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from decimal import Decimal
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace

import pytest
from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

import centermanager.services.admin_data_reset as reset_module
import centermanager.services.enrollment_transfer_service as transfer_module
from centermanager.core.permission_guard import PermissionGuard
from centermanager.database.engine import create_engine_for_path
from centermanager.models.class_ import Class
from centermanager.models.enrollment import Enrollment
from centermanager.models.enrollment_transfer import EnrollmentTransfer
from centermanager.models.income import Income
from centermanager.models.student import Student
from centermanager.models.tuition_adjustment import TuitionAdjustment
from centermanager.models.user import User
from centermanager.repositories.admin_data_reset_repository import AdminDataResetRepository
from centermanager.repositories.provider import SqlAlchemyRepositoryProvider
from centermanager.services.admin_data_reset import AdminDataResetService
from centermanager.services.enrollment_transfer_service import (
    EnrollmentTransferService,
    EnrollmentTransferValidationError,
)
from centermanager.services.tuition_adjustment_service import (
    TuitionAdjustmentService,
    TuitionAdjustmentValidationError,
)


TODAY = date(2026, 9, 26)


class _NoopAudit:
    def record_in_session(self, session, *args, **kwargs):
        return None


class _WritingCollaboration:
    def is_initialized(self):
        return True

    def is_writing(self):
        return True


class _SuccessfulBackup:
    def create_backup(self, label):
        return SimpleNamespace(
            success=True,
            backup_path=Path("backup") / label,
            error=None,
        )


class _FailAfterDeleteRepository(AdminDataResetRepository):
    def delete_tables(self, table_names):
        deleted = super().delete_tables(table_names)
        assert deleted.get("students") == 1
        raise RuntimeError("injected failure after destructive flush")


class _FailAfterDeleteProvider(SqlAlchemyRepositoryProvider):
    def admin_data_resets(self, session):
        return _FailAfterDeleteRepository(session)


def _session_factory(test_db_path):
    engine = create_engine_for_path(test_db_path)
    return engine, sessionmaker(bind=engine, expire_on_commit=False)


def _make_class(name: str, *, capacity: int = 10) -> Class:
    return Class(
        name=name,
        course="Python",
        start_date=date(2026, 9, 1),
        capacity=capacity,
        status="ACTIVE",
        course_fee=1000,
        duration_months=1,
        planned_sessions=10,
        sessions_per_week=2,
    )


def _make_enrollment(student: Student, class_obj: Class) -> Enrollment:
    return Enrollment(
        student_id=student.id,
        class_id=class_obj.id,
        class_name=class_obj.name,
        course_name=class_obj.course,
        start_date=date(2026, 9, 1),
        status="ACTIVE",
        agreed_course_fee=Decimal("1000.0000"),
        planned_sessions=10,
        unit_fee=Decimal("100.0000"),
        enrolled_from_session=1,
        enrolled_until_session=10,
        discount_amount=Decimal("0.0000"),
        billing_policy_version="attendance_v2",
    )


def _seed_transfer_source(session, code: str, source_name: str):
    student = Student(student_code=code, full_name=f"Student {code}")
    source_class = _make_class(source_name)
    session.add_all([student, source_class])
    session.flush()
    enrollment = _make_enrollment(student, source_class)
    session.add(enrollment)
    session.flush()
    return student, source_class, enrollment


def _run_two(barrier: Barrier, left, right):
    def wrapped(call):
        barrier.wait(timeout=10)
        try:
            value = call()
            return ("ok", value)
        except Exception as exc:  # assertions inspect the domain result below
            return ("error", exc)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(wrapped, left)
        second = pool.submit(wrapped, right)
        return first.result(timeout=20), second.result(timeout=20)


def test_concurrent_refunds_cannot_overrun_one_origin_payment(test_db_path, monkeypatch):
    engine, Session = _session_factory(test_db_path)
    try:
        with Session() as session:
            student = Student(student_code="RF-01", full_name="Refund Race")
            class_obj = _make_class("Refund Source")
            session.add_all([student, class_obj])
            session.flush()
            enrollment = _make_enrollment(student, class_obj)
            session.add(enrollment)
            session.flush()
            origin = Income(
                student_id=student.id,
                class_id=class_obj.id,
                enrollment_id=enrollment.id,
                amount=100.0,
                income_type="Tuition",
                payment_method="CASH",
                payment_date=TODAY,
                status=Income.STATUS_ACTIVE,
            )
            session.add(origin)
            session.commit()
            enrollment_id = enrollment.id
            origin_id = origin.id

        # The test target is adjustment serialization/cap enforcement, not RBAC
        # or accounting-period configuration (covered by their own suites).
        monkeypatch.setattr(
            PermissionGuard,
            "require",
            lambda self, permission_name, user=None: None,
        )
        service = TuitionAdjustmentService(
            Session,
            repository_provider=SqlAlchemyRepositoryProvider(),
            audit_service=_NoopAudit(),
        )
        service._ensure_date_mutable = lambda session, value: (
            SimpleNamespace(id=None),
            date(2026, 9, 1),
        )

        barrier = Barrier(2)
        result_a, result_b = _run_two(
            barrier,
            lambda: service.refund(
                enrollment_id,
                80,
                "CASH",
                TODAY,
                reason="Concurrent refund A",
                idempotency_key="refund-race-a",
                origin_income_id=origin_id,
            ),
            lambda: service.refund(
                enrollment_id,
                80,
                "CASH",
                TODAY,
                reason="Concurrent refund B",
                idempotency_key="refund-race-b",
                origin_income_id=origin_id,
            ),
        )

        results = [result_a, result_b]
        successes = [value for status, value in results if status == "ok"]
        failures = [value for status, value in results if status == "error"]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], TuitionAdjustmentValidationError)
        assert "origin remaining refundable" in str(failures[0])

        with Session() as session:
            adjustments = session.query(TuitionAdjustment).all()
            refund_incomes = session.query(Income).filter(
                Income.enrollment_id == enrollment_id,
                Income.amount < 0,
            ).all()
            assert len(adjustments) == 1
            assert Decimal(adjustments[0].amount) == Decimal("80.0000")
            assert adjustments[0].origin_income_id == origin_id
            assert len(refund_incomes) == 1
            assert refund_incomes[0].amount == -80.0
    finally:
        engine.dispose()


def test_same_source_concurrent_transfer_is_one_idempotent_lifecycle(test_db_path, monkeypatch):
    engine, Session = _session_factory(test_db_path)
    try:
        with Session() as session:
            _, _, source = _seed_transfer_source(session, "TR-01", "Source A")
            target = _make_class("Target A", capacity=5)
            session.add(target)
            session.commit()
            source_id = source.id
            target_id = target.id

        monkeypatch.setattr(transfer_module, "get_current_user", lambda: None)
        service = EnrollmentTransferService(
            Session,
            repository_provider=SqlAlchemyRepositoryProvider(),
            audit_service=_NoopAudit(),
        )
        barrier = Barrier(2)
        left, right = _run_two(
            barrier,
            lambda: service.transfer(
                source_id,
                target_id,
                transferred_credit=0,
                reason="Concurrent replay",
                idempotency_key="same-source-race",
            ),
            lambda: service.transfer(
                source_id,
                target_id,
                transferred_credit=0,
                reason="Concurrent replay",
                idempotency_key="same-source-race",
            ),
        )

        assert left[0] == right[0] == "ok"
        assert left[1].id == right[1].id
        with Session() as session:
            assert session.query(EnrollmentTransfer).count() == 1
            assert session.query(Enrollment).filter(
                Enrollment.class_id == target_id,
                Enrollment.status == "ACTIVE",
            ).count() == 1
            assert session.get(Enrollment, source_id).status == "WITHDRAWN"
    finally:
        engine.dispose()


def test_two_students_competing_for_last_slot_have_one_capacity_winner(test_db_path, monkeypatch):
    engine, Session = _session_factory(test_db_path)
    try:
        with Session() as session:
            _, _, source_a = _seed_transfer_source(session, "TR-02A", "Source B1")
            _, _, source_b = _seed_transfer_source(session, "TR-02B", "Source B2")
            target = _make_class("One Slot", capacity=1)
            session.add(target)
            session.commit()
            source_a_id = source_a.id
            source_b_id = source_b.id
            target_id = target.id

        monkeypatch.setattr(transfer_module, "get_current_user", lambda: None)
        service = EnrollmentTransferService(
            Session,
            repository_provider=SqlAlchemyRepositoryProvider(),
            audit_service=_NoopAudit(),
        )
        barrier = Barrier(2)
        result_a, result_b = _run_two(
            barrier,
            lambda: service.transfer(
                source_a_id,
                target_id,
                transferred_credit=0,
                reason="Race for slot A",
                idempotency_key="last-slot-a",
            ),
            lambda: service.transfer(
                source_b_id,
                target_id,
                transferred_credit=0,
                reason="Race for slot B",
                idempotency_key="last-slot-b",
            ),
        )

        results = [result_a, result_b]
        successes = [value for status, value in results if status == "ok"]
        failures = [value for status, value in results if status == "error"]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], EnrollmentTransferValidationError)
        assert "capacity" in str(failures[0]).lower()

        with Session() as session:
            assert session.query(EnrollmentTransfer).count() == 1
            assert session.query(Enrollment).filter(
                Enrollment.class_id == target_id,
                Enrollment.status == "ACTIVE",
            ).count() == 1
            source_states = {
                session.get(Enrollment, source_a_id).status,
                session.get(Enrollment, source_b_id).status,
            }
            assert source_states == {"ACTIVE", "WITHDRAWN"}
    finally:
        engine.dispose()


def test_prepaid_credit_cannot_be_consumed_twice_by_concurrent_transfers(test_db_path, monkeypatch):
    engine, Session = _session_factory(test_db_path)
    try:
        with Session() as session:
            student, source_class, source = _seed_transfer_source(
                session, "TR-03", "Prepaid Source"
            )
            target_a = _make_class("Prepaid Target A")
            target_b = _make_class("Prepaid Target B")
            session.add_all([target_a, target_b])
            session.flush()
            session.add(
                Income(
                    student_id=student.id,
                    class_id=source_class.id,
                    enrollment_id=source.id,
                    amount=500.0,
                    income_type="Tuition",
                    payment_method="CASH",
                    payment_date=TODAY,
                    status=Income.STATUS_ACTIVE,
                )
            )
            session.commit()
            source_id = source.id
            target_a_id = target_a.id
            target_b_id = target_b.id

        monkeypatch.setattr(transfer_module, "get_current_user", lambda: None)
        service = EnrollmentTransferService(
            Session,
            repository_provider=SqlAlchemyRepositoryProvider(),
            audit_service=_NoopAudit(),
        )
        barrier = Barrier(2)
        result_a, result_b = _run_two(
            barrier,
            lambda: service.transfer(
                source_id,
                target_a_id,
                transferred_credit=500,
                reason="Use prepaid A",
                idempotency_key="prepaid-race-a",
            ),
            lambda: service.transfer(
                source_id,
                target_b_id,
                transferred_credit=500,
                reason="Use prepaid B",
                idempotency_key="prepaid-race-b",
            ),
        )

        results = [result_a, result_b]
        successes = [value for status, value in results if status == "ok"]
        failures = [value for status, value in results if status == "error"]
        assert len(successes) == 1
        assert len(failures) == 1
        assert isinstance(failures[0], EnrollmentTransferValidationError)
        assert "already completed a different transfer" in str(failures[0])

        with Session() as session:
            transfers = session.query(EnrollmentTransfer).all()
            assert len(transfers) == 1
            total_credit = session.query(
                func.coalesce(func.sum(EnrollmentTransfer.transferred_credit), 0)
            ).scalar()
            assert Decimal(total_credit) == Decimal("500.0000")
    finally:
        engine.dispose()


def test_admin_reset_failure_after_real_delete_flush_rolls_back_all_rows(
    test_db_path, monkeypatch
):
    engine, Session = _session_factory(test_db_path)
    try:
        with Session() as session:
            session.add(Student(student_code="RST-01", full_name="Rollback Student"))
            session.add(
                User(
                    username="protected-user",
                    password_hash="hash",
                    full_name="Protected User",
                )
            )
            session.commit()

        monkeypatch.setattr(
            reset_module,
            "get_current_user",
            lambda: SimpleNamespace(id=1, username="admin", is_admin=True),
        )
        service = AdminDataResetService(
            Session,
            collaboration_manager=_WritingCollaboration(),
            backup_service=_SuccessfulBackup(),
            audit_service=_NoopAudit(),
            repository_provider=_FailAfterDeleteProvider(),
        )

        with pytest.raises(RuntimeError, match="injected failure after destructive flush"):
            service.reset(
                "student",
                reason="Prove transactional rollback",
                confirmation="RESET STUDENT",
            )

        # A fresh session must see the pre-reset state, proving that the flushed
        # DELETEs were rolled back rather than merely hidden in the failed session.
        with Session() as session:
            assert session.query(Student).filter(
                Student.student_code == "RST-01"
            ).count() == 1
            assert session.query(User).filter(
                User.username == "protected-user"
            ).count() == 1
    finally:
        engine.dispose()
