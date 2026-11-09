"""Isolated read-model tests; never mutate a real SQLCipher runtime."""
from datetime import date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from centermanager.database.base import Base
from centermanager import models  # noqa: F401
from centermanager.models.class_ import Class
from centermanager.models.enrollment import Enrollment
from centermanager.models.monthly_tuition import (
    EnrollmentMonthlyTuitionTerm, MonthlyTuitionAllocationRecord,
    MonthlyTuitionOutcomeRecord, MonthlyTuitionPlanRecord,
)
from centermanager.models.session import Session
from centermanager.services.monthly_tuition_read_model import MonthlyTuitionReadModel
from centermanager.services.tuition_accrual_service import TuitionAccrualUnresolvedError


@pytest.fixture()
def monthly_db():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine)
    with factory() as db:
        klass = Class(name="Monthly testing", status="ACTIVE")
        db.add(klass)
        db.flush()
        enrollment = Enrollment(
            class_id=klass.id, student_id=1, status="ACTIVE",
            start_date=date(2039, 12, 1),
            agreed_course_fee=Decimal("800000"), planned_sessions=2,
            unit_fee=Decimal("400000"), enrolled_from_session=1,
            enrolled_until_session=2, discount_amount=Decimal("0"),
            billing_policy_version="attendance_v2",
        )
        s1 = Session(class_id=klass.id, session_number=1, title="S1",
                     scheduled_date=date(2040, 1, 1), status="Completed")
        s2 = Session(class_id=klass.id, session_number=2, title="S2",
                     scheduled_date=date(2040, 1, 8), status="Completed")
        plan = MonthlyTuitionPlanRecord(
            class_id=klass.id, month=date(2040, 1, 1), version=1,
            monthly_fee_vnd=800000, schedule_version="v1", status="ACTIVE")
        db.add_all([enrollment, s1, s2, plan])
        db.flush()
        db.add_all([
            MonthlyTuitionAllocationRecord(plan_id=plan.id, session_id=s1.id,
                                          original_date=s1.scheduled_date, amount_vnd=400000),
            MonthlyTuitionAllocationRecord(plan_id=plan.id, session_id=s2.id,
                                          original_date=s2.scheduled_date, amount_vnd=400000),
            EnrollmentMonthlyTuitionTerm(
                enrollment_id=enrollment.id, effective_from=date(2040, 1, 1),
                activated_at=datetime(2039, 12, 1), activated_by="admin"),
        ])
        db.commit()
    yield factory
    engine.dispose()


def test_as_of_monthly_accrual_and_legacy_boundary(monthly_db):
    with monthly_db() as db:
        enrollment = db.get(Enrollment, 1)
        sessions = db.query(Session).all()
        result = MonthlyTuitionReadModel.project(db, enrollment, sessions, date(2040, 1, 1))
        assert result.accrued_vnd == Decimal("400000")
        assert result.historical_legacy_vnd == Decimal("0")
        assert result.monthly_vnd == Decimal("400000")
        full = MonthlyTuitionReadModel.project(db, enrollment, sessions, date(2040, 1, 31))
        assert full.accrued_vnd == Decimal("800000")


def test_cancelled_session_requires_approved_outcome(monthly_db):
    with monthly_db() as db:
        enrollment = db.get(Enrollment, 1)
        sessions = db.query(Session).order_by(Session.id).all()
        sessions[0].status = "Cancelled"
        db.flush()
        with pytest.raises(TuitionAccrualUnresolvedError):
            MonthlyTuitionReadModel.project(db, enrollment, sessions, date(2040, 1, 31))
        db.add(MonthlyTuitionOutcomeRecord(
            enrollment_id=enrollment.id, session_id=sessions[0].id, revision=1,
            outcome="CENTRE_CANCELLED_NO_MAKEUP", reason="Center closure",
            idempotency_key="centre-cancel-enrollment-1-session-1",
            effective_date=date(2040, 1, 2),
            recorded_at=datetime(2040, 1, 2), recorded_by="admin",
        ))
        db.flush()
        value = MonthlyTuitionReadModel.project(db, enrollment, sessions, date(2040, 1, 31))
        assert value.cancelled_vnd == Decimal("400000")
        assert value.accrued_vnd == Decimal("400000")

def test_finance_outcome_command_is_idempotent_and_reconciles(monthly_db, monkeypatch):
    from types import SimpleNamespace
    import centermanager.services.monthly_tuition_outcome_service as outcome_module
    from centermanager.services.monthly_tuition_outcome_service import (
        MonthlyTuitionOutcomeService, MonthlyOutcomeError
    )
    from centermanager.services.monthly_tuition_ledger_projection import SessionBillingOutcome
    monkeypatch.setattr(outcome_module, "get_current_user",
                        lambda: SimpleNamespace(username="finance_operator"))
    with monthly_db() as db:
        first_session = db.query(Session).order_by(Session.id).first()
        first_session.status = "Cancelled"
        db.commit()
    service = MonthlyTuitionOutcomeService(monthly_db)
    create = MonthlyTuitionOutcomeService.record_outcome.__wrapped__
    event_id = create(
        service, 1, 1, SessionBillingOutcome.CENTRE_CANCELLED_NO_MAKEUP,
        reason="Center closed", idempotency_key="cancel-1"
    )
    assert create(
        service, 1, 1, SessionBillingOutcome.CENTRE_CANCELLED_NO_MAKEUP,
        reason="Center closed", idempotency_key="cancel-1"
    ) == event_id
    with pytest.raises(MonthlyOutcomeError):
        create(
            service, 1, 1, SessionBillingOutcome.CENTRE_CANCELLED_NO_MAKEUP,
            reason="Different reason", idempotency_key="cancel-1"
        )
    with monthly_db() as db:
        assert db.query(MonthlyTuitionOutcomeRecord).count() == 1
        accrual = MonthlyTuitionReadModel.project(
            db, db.get(Enrollment, 1), db.query(Session).all(), date(2040, 1, 31)
        )
        assert accrual.monthly_vnd == Decimal("400000")

def test_future_month_enrollment_opt_in_is_explicit(monthly_db, monkeypatch):
    from types import SimpleNamespace
    import centermanager.services.monthly_tuition_enrollment_service as activation
    from centermanager.services.monthly_tuition_enrollment_service import (
        MonthlyTuitionEnrollmentService, MonthlyEnrollmentActivationError
    )
    monkeypatch.setattr(activation, "get_current_user",
                        lambda: SimpleNamespace(username="authorized_manager"))
    with monthly_db() as db:
        db.query(EnrollmentMonthlyTuitionTerm).delete()
        db.commit()
    from centermanager.core.clock import get_clock
    from centermanager.services.monthly_tuition_migration_gate import EnrollmentMigrationEvidence
    today = get_clock().today()
    def verified_preflight(db, enrollment, effective_date):
        return EnrollmentMigrationEvidence(
            enrollment_id=enrollment.id, requested_effective_date=effective_date,
            review_date=today, first_enrollment_date=enrollment.start_date,
            legacy_tuition_resolved=enrollment.has_tuition_contract,
            has_unattributed_payment=False, already_monthly=False,
            has_unresolved_reconciliation=False,
            encrypted_backup_verified=True, write_authority_verified=True,
        )
    service = MonthlyTuitionEnrollmentService(
        monthly_db, verified_preflight=verified_preflight,
    )
    activate = MonthlyTuitionEnrollmentService.activate_future_month.__wrapped__
    term_id = activate(service, 1, date(2040, 1, 1))
    with monthly_db() as db:
        term = db.get(EnrollmentMonthlyTuitionTerm, term_id)
        assert term.enrollment_id == 1
        assert term.activated_by == "authorized_manager"
        # The legacy immutable policy snapshot is still intact.
        assert db.get(Enrollment, 1).billing_policy_version == "attendance_v2"
    with pytest.raises(MonthlyEnrollmentActivationError):
        activate(service, 1, date(2040, 1, 1))

def test_outstanding_uses_opt_in_monthly_accrual(monthly_db):
    from types import SimpleNamespace
    from centermanager.services.outstanding_service import OutstandingService

    provider = SimpleNamespace(sessions=lambda db: SimpleNamespace(
        get_by_class=lambda class_id: db.query(Session).filter(
            Session.class_id == class_id
        ).all()
    ))
    service = OutstandingService(monthly_db, repository_provider=provider)
    with monthly_db() as db:
        enrollment = db.get(Enrollment, 1)
        accrued, configured = service._calculate_accrued(
            db, enrollment, as_of_date=date(2040, 1, 31)
        )
        assert configured and accrued == Decimal("800000")

def test_class_cancellation_is_atomic_and_idempotent(monthly_db, monkeypatch):
    from types import SimpleNamespace
    import centermanager.services.monthly_tuition_class_cancellation as module
    from centermanager.services.monthly_tuition_class_cancellation import (
        MonthlyTuitionClassCancellationService,
    )
    monkeypatch.setattr(module, "get_current_user",
                        lambda: SimpleNamespace(username="finance_manager"))
    with monthly_db() as db:
        first = db.query(Session).order_by(Session.id).first()
        first.status = "Cancelled"
        db.commit()
    service = MonthlyTuitionClassCancellationService(monthly_db)
    apply = MonthlyTuitionClassCancellationService.approve_no_makeup.__wrapped__
    assert apply(service, 1, 1, reason="Center closure") == 1
    assert apply(service, 1, 1, reason="Center closure") == 0
    with monthly_db() as db:
        assert db.query(MonthlyTuitionOutcomeRecord).count() == 1
        result = MonthlyTuitionReadModel.project(
            db, db.get(Enrollment, 1), db.query(Session).all(), date(2040, 1, 31)
        )
        assert result.cancelled_vnd == Decimal("400000")

def test_midmonth_join_uses_only_remaining_original_sessions(monthly_db):
    with monthly_db() as db:
        enrollment = db.get(Enrollment, 1)
        enrollment.start_date = date(2040, 1, 8)
        db.flush()
        projection = MonthlyTuitionReadModel.project(
            db, enrollment, db.query(Session).all(), date(2040, 1, 31)
        )
        assert projection.monthly_vnd == Decimal("400000")
        assert projection.cancelled_vnd == Decimal("0")


def test_group_a_f04_rejects_activation_without_verified_backup_or_write(monthly_db, monkeypatch):
    from types import SimpleNamespace
    import centermanager.services.monthly_tuition_enrollment_service as activation
    from centermanager.services.monthly_tuition_enrollment_service import (
        MonthlyTuitionEnrollmentService, MonthlyEnrollmentActivationError,
    )
    from centermanager.services.monthly_tuition_migration_gate import EnrollmentMigrationEvidence
    from centermanager.core.clock import get_clock
    monkeypatch.setattr(activation, "get_current_user",
                        lambda: SimpleNamespace(username="finance_manager"))
    with monthly_db() as db:
        db.query(EnrollmentMonthlyTuitionTerm).delete()
        db.commit()
    command = MonthlyTuitionEnrollmentService.activate_future_month.__wrapped__
    with pytest.raises(MonthlyEnrollmentActivationError, match="Verified encrypted backup"):
        command(MonthlyTuitionEnrollmentService(monthly_db), 1, date(2040, 1, 1))
    today = get_clock().today()
    def failed_preflight(db, enrollment, start):
        return EnrollmentMigrationEvidence(
            enrollment_id=enrollment.id, requested_effective_date=start,
            review_date=today, first_enrollment_date=date(2039, 12, 1),
            legacy_tuition_resolved=True, has_unattributed_payment=False,
            already_monthly=False, has_unresolved_reconciliation=False,
            encrypted_backup_verified=False, write_authority_verified=True,
        )
    with pytest.raises(MonthlyEnrollmentActivationError, match="NO_BACKUP"):
        command(MonthlyTuitionEnrollmentService(monthly_db, verified_preflight=failed_preflight),
                1, date(2040, 1, 1))


def test_group_a_f03_quote_one_month_and_midmonth_join(monthly_db):
    from centermanager.services.monthly_tuition_quote_service import MonthlyTuitionQuoteService
    service = MonthlyTuitionQuoteService(monthly_db)
    quote = service.quote(1, date(2040, 1, 1), 1)
    assert quote.amount_vnd == 800000
    assert quote.payment_period == "TUITION_MONTH:2040-01-01"
    with monthly_db() as db:
        db.get(Enrollment, 1).start_date = date(2040, 1, 8)
        db.commit()
    partial = service.quote(1, date(2040, 1, 1), 1)
    assert partial.amount_vnd == 400000
    assert partial.lines[0].chargeable_sessions == 1


def test_group_a_f03_quarter_quote_is_one_receipt_amount(monthly_db):
    from centermanager.services.monthly_tuition_quote_service import (
        MonthlyTuitionQuoteService, MonthlyTuitionQuoteError,
    )
    service = MonthlyTuitionQuoteService(monthly_db)
    with pytest.raises(MonthlyTuitionQuoteError, match="Activated tuition plan missing"):
        service.quote(1, date(2040, 1, 1), 3)
    with monthly_db() as db:
        klass = db.get(Class, 1)
        for month in (2, 3):
            lesson = Session(class_id=klass.id, session_number=month+1,
                             title="Month lesson", scheduled_date=date(2040, month, 8),
                             status="Scheduled")
            db.add(lesson)
            db.flush()
            plan = MonthlyTuitionPlanRecord(
                class_id=klass.id, month=date(2040, month, 1), version=1,
                monthly_fee_vnd=800000, schedule_version="v1", status="ACTIVE",
            )
            db.add(plan)
            db.flush()
            db.add(MonthlyTuitionAllocationRecord(
                plan_id=plan.id, session_id=lesson.id,
                original_date=lesson.scheduled_date, amount_vnd=800000,
            ))
        db.commit()
    quote = service.quote(1, date(2040, 1, 1), 3)
    assert quote.amount_vnd == 2400000
    assert [line.amount_vnd for line in quote.lines] == [800000, 800000, 800000]
    assert quote.payment_period == "TUITION_QUARTER:2040-01-01"


def test_group_a_f02_legacy_cancel_guard_protects_activated_monthly_term(monthly_db):
    from centermanager.services.session_service import SessionService, SessionValidationError
    service = SessionService(monthly_db)
    with monthly_db() as db:
        lesson = db.get(Session, 1)
        with pytest.raises(SessionValidationError, match="monthly tuition allocations"):
            service._protect_monthly_billing(db, lesson)


def test_group_a_f02_atomic_cancel_waiver_is_idempotent(monthly_db, monkeypatch):
    from types import SimpleNamespace
    import centermanager.services.monthly_tuition_class_cancellation as module
    from centermanager.services.monthly_tuition_class_cancellation import (
        MonthlyTuitionClassCancellationService,
    )
    monkeypatch.setattr(module, "get_current_user",
                        lambda: SimpleNamespace(username="finance_manager"))
    with monthly_db() as db:
        db.get(Session, 1).status = "Scheduled"
        db.commit()
    service = MonthlyTuitionClassCancellationService(monthly_db)
    assert service._apply_no_makeup(1, 1, reason="No makeup", cancel_first=True) == 1
    assert service._apply_no_makeup(1, 1, reason="No makeup", cancel_first=True) == 0
    with monthly_db() as db:
        assert db.get(Session, 1).status == "Cancelled"
        assert db.query(MonthlyTuitionOutcomeRecord).count() == 1
        projection = MonthlyTuitionReadModel.project(
            db, db.get(Enrollment, 1), db.query(Session).all(), date(2040, 1, 31),
        )
        assert projection.cancelled_vnd == Decimal("400000")


def test_group_a_f02_unresolved_monthly_cancellation_does_not_appear_as_zero_debt(monthly_db):
    from centermanager.services.outstanding_service import OutstandingService
    from types import SimpleNamespace
    with monthly_db() as db:
        db.get(Session, 1).status = "Cancelled"
        db.flush()
        provider = SimpleNamespace(sessions=lambda _: SimpleNamespace(
            get_by_class=lambda class_id: db.query(Session).filter(
                Session.class_id == class_id,
            ).all(),
        ))
        service = OutstandingService(monthly_db, repository_provider=provider)
        with pytest.raises(TuitionAccrualUnresolvedError, match="approved billing outcome"):
            service._calculate_accrued(db, db.get(Enrollment, 1),
                                       as_of_date=date(2040, 1, 31))


def test_group_a_f01_income_picker_uses_same_accrual_as_outstanding(monthly_db, monkeypatch):
    from types import SimpleNamespace
    from centermanager.services.income_service import IncomeService
    import centermanager.services.income_service as income_module
    from centermanager.services.monthly_tuition_read_model import calculate_effective_tuition_accrual
    monkeypatch.setattr(income_module, "get_clock", lambda: SimpleNamespace(
        today=lambda: date(2040, 1, 31),
    ))
    with monthly_db() as db:
        enrollment = db.get(Enrollment, 1)
        provider = SimpleNamespace(
            students=lambda _: SimpleNamespace(get_by_id=lambda _: SimpleNamespace(
                full_name="Test student", student_code="S001", status="ACTIVE",
            )),
            classes=lambda _: SimpleNamespace(get_by_id=lambda _: db.get(Class, 1)),
            sessions=lambda _: SimpleNamespace(get_by_class=lambda _: db.query(Session).all()),
            incomes=lambda _: SimpleNamespace(sum_active_tuition_for_enrollment=lambda *a, **kw: 0),
        )
        service = IncomeService.__new__(IncomeService)
        service._repository_provider = provider
        choice = service._tuition_choice_from_enrollment(db, enrollment)
        expected = calculate_effective_tuition_accrual(
            db, enrollment, db.query(Session).all(), date(2040, 1, 31),
        )
        assert choice.outstanding == expected == Decimal("800000")
        assert choice.balance_state == "OWED"


def test_group_a_f04_verified_backup_write_preflight(tmp_path, monthly_db, monkeypatch):
    import json
    from types import SimpleNamespace
    from datetime import datetime
    import centermanager.services.monthly_tuition_verified_preflight as module
    from centermanager.services.monthly_tuition_verified_preflight import VerifiedMonthlyTuitionPreflight
    from centermanager.services.monthly_tuition_migration_gate import assess_enrollment_migration
    backup = tmp_path / "managed_backup"
    backup.mkdir()
    (backup / "manifest.json").write_text(json.dumps({
        "database_encrypted": True, "created_at": datetime.now().isoformat(),
    }), encoding="utf-8")
    monkeypatch.setattr(module, "database_encryption_required", lambda: True)
    with monthly_db() as db:
        db.query(EnrollmentMonthlyTuitionTerm).delete()
        db.commit()
    instance = VerifiedMonthlyTuitionPreflight(
        backup, reconciliation_verifier=lambda db, enrollment: False,
        backup_service=SimpleNamespace(_validate_backup=lambda path: (True, "")),
        write_verifier=lambda: True,
    )
    with monthly_db() as db:
        enrollment = db.get(Enrollment, 1)
        evidence = instance(db, enrollment, date(2040, 1, 1))
        assert assess_enrollment_migration(evidence).may_activate
        (backup / "manifest.json").write_text(json.dumps({
            "database_encrypted": False, "created_at": datetime.now().isoformat(),
        }), encoding="utf-8")
        evidence = instance(db, enrollment, date(2040, 1, 1))
        assert not assess_enrollment_migration(evidence).may_activate


def test_group_a_f02_cancellation_uses_original_month_after_date_change(monthly_db, monkeypatch):
    from types import SimpleNamespace
    import centermanager.services.monthly_tuition_class_cancellation as module
    from centermanager.services.monthly_tuition_class_cancellation import MonthlyTuitionClassCancellationService
    monkeypatch.setattr(module, "get_current_user",
                        lambda: SimpleNamespace(username="finance_manager"))
    with monthly_db() as db:
        lesson = db.get(Session, 1)
        lesson.status = "Scheduled"
        lesson.scheduled_date = date(2040, 2, 2)
        db.commit()
    assert MonthlyTuitionClassCancellationService(monthly_db)._apply_no_makeup(
        1, 1, reason="Rescheduled then no makeup", cancel_first=True,
    ) == 1
    with monthly_db() as db:
        projection = MonthlyTuitionReadModel.project(
            db, db.get(Enrollment, 1), db.query(Session).all(), date(2040, 1, 31),
        )
        assert projection.cancelled_vnd == Decimal("400000")
        assert projection.accrued_vnd == Decimal("400000")


def test_group_a_f02_cancellation_cannot_credit_pre_enrollment_session(monthly_db, monkeypatch):
    from types import SimpleNamespace
    import centermanager.services.monthly_tuition_class_cancellation as module
    from centermanager.services.monthly_tuition_class_cancellation import MonthlyTuitionClassCancellationService
    monkeypatch.setattr(module, "get_current_user",
                        lambda: SimpleNamespace(username="finance_manager"))
    with monthly_db() as db:
        enrollment = db.get(Enrollment, 1)
        enrollment.enrolled_from_session = 2
        lesson = db.get(Session, 1)
        lesson.status = "Scheduled"
        db.commit()
    result = MonthlyTuitionClassCancellationService(monthly_db)._apply_no_makeup(
        1, 1, reason="No makeup", cancel_first=True,
    )
    assert result == 0
    with monthly_db() as db:
        assert db.get(Session, 1).status == "Cancelled"
        assert db.query(MonthlyTuitionOutcomeRecord).count() == 0


def test_group_a_f04_factory_builds_real_trusted_preflight(monthly_db, tmp_path):
    from centermanager.services.monthly_tuition_enrollment_service import MonthlyTuitionEnrollmentService
    from centermanager.services.monthly_tuition_verified_preflight import VerifiedMonthlyTuitionPreflight
    service = MonthlyTuitionEnrollmentService.from_verified_backup(
        monthly_db, backup_path=tmp_path / "backup",
    )
    assert isinstance(service._verified_preflight, VerifiedMonthlyTuitionPreflight)
    # Without a managed verified backup, do not allow fake success.
    assert service._verified_preflight._backup_verified() is False


def test_group_a_f03_quote_blocks_duplicate_cash_and_overlapping_quarter(monthly_db):
    from centermanager.models.income import Income
    from centermanager.services.monthly_tuition_quote_service import (
        MonthlyTuitionQuoteError, MonthlyTuitionQuoteService,
    )
    service = MonthlyTuitionQuoteService(monthly_db)
    with monthly_db() as db:
        payment = Income(
            student_id=1, class_id=1, enrollment_id=1,
            amount=800000, income_type="Tuition", payment_method="BANK",
            payment_date=date(2039, 12, 20),
            payment_period="TUITION_MONTH:2040-01-01",
            status=Income.STATUS_ACTIVE,
        )
        db.add(payment)
        db.commit()
        payment_id = payment.id
    with pytest.raises(MonthlyTuitionQuoteError, match="already covers"):
        service.quote(1, date(2040, 1, 1), 1)
    with pytest.raises(MonthlyTuitionQuoteError, match="already covers"):
        service.quote(1, date(2040, 1, 1), 3)
    with monthly_db() as db:
        db.get(Income, payment_id).status = Income.STATUS_VOIDED
        db.commit()
    assert service.quote(1, date(2040, 1, 1), 1).amount_vnd == 800000


# Group B: immutable billing date, explainable gross/waiver and finance/recovery regression.

def test_f05_reschedule_across_months_keeps_january_accrual(monthly_db):
    with monthly_db() as db:
        enrollment = db.get(Enrollment, 1)
        original = MonthlyTuitionReadModel.project(
            db, enrollment, db.query(Session).all(), date(2040, 1, 31)
        )
        assert original.accrued_vnd == Decimal("800000")
        db.get(Session, 1).scheduled_date = date(2040, 2, 14)
        db.flush()
        january = MonthlyTuitionReadModel.project(
            db, enrollment, db.query(Session).all(), date(2040, 1, 31)
        )
        february = MonthlyTuitionReadModel.project(
            db, enrollment, db.query(Session).all(), date(2040, 2, 28)
        )
        assert january.accrued_vnd == original.accrued_vnd == february.accrued_vnd
        assert dict(january.monthly_original_dates)[1] == date(2040, 1, 1)
        db.get(Session, 1).scheduled_date = date(2039, 12, 20)
        db.flush()
        earlier = MonthlyTuitionReadModel.project(
            db, enrollment, db.query(Session).all(), date(2040, 1, 31)
        )
        assert earlier.accrued_vnd == original.accrued_vnd


def test_f05_legacy_session_delete_guard_preserves_immutable_allocation(monthly_db):
    from centermanager.services.session_service import SessionService, SessionValidationError
    service = SessionService(monthly_db)
    with monthly_db() as db:
        with pytest.raises(SessionValidationError, match="monthly tuition allocations"):
            service._protect_monthly_billing(db, db.get(Session, 1))
        assert db.query(MonthlyTuitionAllocationRecord).count() == 2


def test_f06_explainable_monthly_gross_waiver_and_original_dates(monthly_db):
    from centermanager.models.student import Student
    from centermanager.services.tuition_detail_service import TuitionDetailService
    from centermanager.models.monthly_tuition import MonthlyTuitionOutcomeRecord
    with monthly_db() as db:
        db.add(Student(id=1, student_code="STU001", full_name="AnTechKids Test"))
        lesson = db.get(Session, 1)
        lesson.status = "Cancelled"
        lesson.scheduled_date = date(2040, 2, 15)
        db.add(MonthlyTuitionOutcomeRecord(
            enrollment_id=1, session_id=1, revision=1,
            outcome="CENTRE_CANCELLED_NO_MAKEUP", reason="Closed",
            idempotency_key="f06-cancel-1", effective_date=date(2040, 1, 2),
            recorded_at=datetime(2040, 1, 2), recorded_by="manager",
        ))
        db.commit()
    result = TuitionDetailService(monthly_db).get_detail(1, as_of_date=date(2040, 1, 31))
    assert result.is_monthly_policy
    assert result.monthly_gross_accrued == Decimal("800000")
    assert result.monthly_waived == Decimal("400000")
    assert result.gross_accrued == Decimal("800000")
    assert result.recognized_discount == Decimal("400000")
    assert result.net_accrued == Decimal("400000")
    assert result.gross_accrued - result.recognized_discount == result.net_accrued
    assert result.sessions[0].original_billing_date == date(2040, 1, 1)
    assert result.sessions[0].scheduled_date == date(2040, 2, 15)
    assert result.sessions[0].waived_amount == Decimal("400000")
    assert result.sessions[0].billing_contribution == Decimal("0")


def test_f07_cancellation_rollback_preserves_session_wallet_and_outcomes(monthly_db, monkeypatch):
    import centermanager.services.monthly_tuition_class_cancellation as module
    from centermanager.services.monthly_tuition_class_cancellation import (
        MonthlyTuitionClassCancellationService,
    )
    from types import SimpleNamespace
    monkeypatch.setattr(module, "get_current_user",
                        lambda: SimpleNamespace(username="finance_manager"))
    with monthly_db() as db:
        db.get(Session, 1).status = "Scheduled"
        db.commit()
    def force_recovery_failure(*args, **kwargs):
        raise RuntimeError("simulated WRITE/recovery outbox refusal")
    monkeypatch.setattr(module, "record_for_active_write", force_recovery_failure)
    with pytest.raises(RuntimeError, match="recovery outbox"):
        MonthlyTuitionClassCancellationService(monthly_db)._apply_no_makeup(
            1, 1, reason="No makeup", cancel_first=True,
        )
    with monthly_db() as db:
        assert db.get(Session, 1).status == "Scheduled"
        assert db.query(MonthlyTuitionOutcomeRecord).count() == 0
        from centermanager.models.income import Income
        assert db.query(Income).count() == 0


def test_f07_wallet_income_outstanding_and_repeated_waiver(monthly_db, monkeypatch):
    from types import SimpleNamespace
    from centermanager.models.income import Income
    from centermanager.services.monthly_tuition_read_model import calculate_effective_tuition_accrual
    from centermanager.services.outstanding_service import OutstandingService
    from centermanager.services.monthly_tuition_class_cancellation import (
        MonthlyTuitionClassCancellationService,
    )
    import centermanager.services.monthly_tuition_class_cancellation as module
    monkeypatch.setattr(module, "get_current_user",
                        lambda: SimpleNamespace(username="finance_manager"))
    with monthly_db() as db:
        db.get(Session, 1).status = "Scheduled"
        db.add(Income(student_id=1, class_id=1, enrollment_id=1, amount=800000,
                      income_type="Tuition", payment_method="BANK",
                      payment_date=date(2039, 12, 20),
                      payment_period="TUITION_MONTH:2040-01-01",
                      status=Income.STATUS_ACTIVE))
        db.commit()
    cancellation = MonthlyTuitionClassCancellationService(monthly_db)
    assert cancellation._apply_no_makeup(1, 1, reason="Center closed", cancel_first=True) == 1
    assert cancellation._apply_no_makeup(1, 1, reason="Center closed", cancel_first=True) == 0
    with monthly_db() as db:
        enrollment = db.get(Enrollment, 1)
        sessions = db.query(Session).all()
        accrued = calculate_effective_tuition_accrual(
            db, enrollment, sessions, date(2040, 1, 31),
        )
        paid = sum(Decimal(str(row.amount)) for row in db.query(Income).all())
        provider = type("SessionProvider", (), {
            "sessions": lambda self, session: type("Repo", (), {
                "get_by_class": lambda self, class_id: sessions
            })()
        })()
        resolved, configured = OutstandingService(
            monthly_db, repository_provider=provider,
        )._calculate_accrued(db, enrollment, as_of_date=date(2040, 1, 31))
        assert configured and resolved == accrued == Decimal("400000")
        assert paid == Decimal("800000")
        assert paid - accrued == Decimal("400000")
        assert db.query(MonthlyTuitionOutcomeRecord).count() == 1
        assert db.query(Income).count() == 1


def test_f05_reopening_monthly_cancelled_lesson_requires_finance_reversal(monthly_db):
    from centermanager.services.session_service import SessionService, SessionValidationError
    with monthly_db() as db:
        db.get(Session, 1).status = "Cancelled"
        db.commit()
    service = SessionService(monthly_db)
    with pytest.raises(SessionValidationError, match="monthly tuition allocations"):
        SessionService.update_session.__wrapped__(service, 1, status="Scheduled")
    with monthly_db() as db:
        assert db.get(Session, 1).status == "Cancelled"
        assert db.query(MonthlyTuitionAllocationRecord).count() == 2


def test_f05_approved_replacement_makeup_in_next_month_has_no_second_fee(monthly_db):
    with monthly_db() as db:
        replacement = Session(
            class_id=1, session_number=3, title="Makeup",
            scheduled_date=date(2040, 2, 9), status="Scheduled",
        )
        db.add(replacement)
        db.flush()
        db.add(MonthlyTuitionOutcomeRecord(
            enrollment_id=1, session_id=1, revision=1,
            outcome="RESCHEDULED", reason="Official makeup",
            replacement_session_id=replacement.id,
            idempotency_key="f05-replacement-1",
            effective_date=date(2040, 1, 2),
            recorded_at=datetime(2040, 1, 2), recorded_by="manager",
        ))
        db.flush()
        full = MonthlyTuitionReadModel.project(
            db, db.get(Enrollment, 1), db.query(Session).all(),
            date(2040, 2, 28),
        )
        assert full.accrued_vnd == Decimal("800000")
        assert full.cancelled_vnd == Decimal("0")
        assert set(dict(full.monthly_contributions)) == {1, 2}


def test_f06_detail_fails_closed_on_unresolved_activated_contract(monthly_db):
    from centermanager.models.student import Student
    from centermanager.services.tuition_detail_service import TuitionDetailService
    with monthly_db() as db:
        db.add(Student(id=1, student_code="STU001", full_name="AnTechKids Test"))
        db.get(Enrollment, 1).agreed_course_fee = None
        db.commit()
    with pytest.raises(TuitionAccrualUnresolvedError, match="unresolved historical"):
        TuitionDetailService(monthly_db).get_detail(
            1, as_of_date=date(2040, 1, 31),
        )


def test_f05_pre_optin_active_class_plan_stays_legacy_for_later_joiner(monthly_db):
    with monthly_db() as db:
        term = db.query(EnrollmentMonthlyTuitionTerm).one()
        term.effective_from = date(2040, 2, 1)
        lesson = Session(class_id=1, session_number=3, title="Feb lesson",
                         scheduled_date=date(2040, 2, 8), status="Completed")
        db.add(lesson)
        db.flush()
        plan = MonthlyTuitionPlanRecord(
            class_id=1, month=date(2040, 2, 1), version=1,
            monthly_fee_vnd=500000, schedule_version="feb", status="ACTIVE",
        )
        db.add(plan)
        db.flush()
        db.add(MonthlyTuitionAllocationRecord(
            plan_id=plan.id, session_id=lesson.id,
            original_date=lesson.scheduled_date, amount_vnd=500000,
        ))
        db.flush()
        projected = MonthlyTuitionReadModel.project(
            db, db.get(Enrollment, 1), db.query(Session).all(),
            date(2040, 2, 28),
        )
        assert projected.historical_legacy_vnd == Decimal("800000")
        assert projected.monthly_vnd == Decimal("500000")
        assert projected.accrued_vnd == Decimal("1300000")
