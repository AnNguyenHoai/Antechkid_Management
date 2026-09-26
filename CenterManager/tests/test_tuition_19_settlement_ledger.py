# -*- coding: utf-8 -*-
"""TUITION-19 settlement-ledger reconciliation coverage."""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from centermanager.database.engine import create_engine_for_path
from centermanager.models.class_ import Class
from centermanager.models.enrollment import Enrollment
from centermanager.models.enrollment_transfer import EnrollmentTransfer
from centermanager.models.income import Income
from centermanager.models.student import Student
from centermanager.models.tuition_adjustment import TuitionAdjustment
from centermanager.repositories.income_repository import (
    IncomeRepository,
    TuitionSettlementComponent,
)
from centermanager.services.tuition_detail_service import TuitionDetailService


def _seed_enrollments(session):
    student = Student(student_code="TU19-001", full_name="Tuition 19 Student")
    classes = [Class(name=f"TU19 Class {index}") for index in range(1, 4)]
    session.add_all([student, *classes])
    session.flush()

    enrollments = [
        Enrollment(student_id=student.id, class_id=class_obj.id, class_name=class_obj.name)
        for class_obj in classes
    ]
    session.add_all(enrollments)
    session.flush()
    return enrollments


def _seed_settlement_history(session, enrollment_id: int, target_id: int, incoming_source_id: int):
    payment = Income(
        enrollment_id=enrollment_id,
        amount=100,
        income_type="Tuition",
        payment_method="CASH",
        payment_date=date(2026, 1, 1),
        status=Income.STATUS_ACTIVE,
        note="Initial payment",
    )
    refund_income = Income(
        enrollment_id=enrollment_id,
        amount=-20,
        income_type="Tuition",
        payment_method="BANK",
        payment_date=date(2026, 1, 2),
        status=Income.STATUS_ACTIVE,
        note="Cash refund",
    )
    session.add_all([payment, refund_income])
    session.flush()

    # The REFUND adjustment is audit evidence for the negative Income row and
    # must not become a second settlement component.
    refund_adjustment = TuitionAdjustment(
        enrollment_id=enrollment_id,
        linked_income_id=refund_income.id,
        kind=TuitionAdjustment.KIND_REFUND,
        amount=Decimal("20"),
        adjustment_date=date(2026, 1, 2),
        wallet="BANK",
        reason="Refund evidence",
        idempotency_key="tu19-refund",
    )
    credit_adjustment = TuitionAdjustment(
        enrollment_id=enrollment_id,
        kind=TuitionAdjustment.KIND_CREDIT,
        amount=Decimal("15"),
        adjustment_date=date(2026, 1, 3),
        reason="Non-cash goodwill credit",
        idempotency_key="tu19-credit",
    )
    outgoing = EnrollmentTransfer(
        source_enrollment_id=enrollment_id,
        target_enrollment_id=target_id,
        idempotency_key="tu19-transfer-out",
        transferred_credit=Decimal("10"),
        source_balance_before=Decimal("10"),
        reason="Move prepaid credit out",
        transferred_at=datetime(2026, 1, 4, 10, 0, 0),
    )
    incoming = EnrollmentTransfer(
        source_enrollment_id=incoming_source_id,
        target_enrollment_id=enrollment_id,
        idempotency_key="tu19-transfer-in",
        transferred_credit=Decimal("5"),
        source_balance_before=Decimal("5"),
        reason="Move prepaid credit in",
        transferred_at=datetime(2026, 1, 5, 10, 0, 0),
    )
    session.add_all([refund_adjustment, credit_adjustment, outgoing, incoming])
    session.commit()


def test_settlement_components_reconcile_all_supported_effects_without_double_refund(test_db_path):
    engine = create_engine_for_path(test_db_path)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with SessionFactory() as session:
            source, target, incoming_source = _seed_enrollments(session)
            _seed_settlement_history(session, source.id, target.id, incoming_source.id)

            repo = IncomeRepository(session)
            components = repo.list_active_tuition_settlement_components(
                source.id,
                as_of_date=date(2026, 1, 31),
            )

            assert [item.kind for item in components] == [
                TuitionSettlementComponent.KIND_PAYMENT,
                TuitionSettlementComponent.KIND_REFUND,
                TuitionSettlementComponent.KIND_CREDIT_ADJUSTMENT,
                TuitionSettlementComponent.KIND_TRANSFER_OUT,
                TuitionSettlementComponent.KIND_TRANSFER_IN,
            ]
            assert [item.amount for item in components] == [
                Decimal("100.0"),
                Decimal("-20.0"),
                Decimal("15.0000"),
                Decimal("-10.0000"),
                Decimal("5.0000"),
            ]
            assert sum((item.amount for item in components), Decimal("0")) == Decimal("90")
            assert repo.sum_active_tuition_for_enrollment(
                source.id,
                as_of_date=date(2026, 1, 31),
            ) == Decimal("90")

            refund_rows = [
                item
                for item in components
                if item.kind == TuitionSettlementComponent.KIND_REFUND
            ]
            assert len(refund_rows) == 1
            assert refund_rows[0].source == TuitionSettlementComponent.SOURCE_INCOME
    finally:
        engine.dispose()


def test_settlement_components_apply_the_same_as_of_cutoff_to_every_source(test_db_path):
    engine = create_engine_for_path(test_db_path)
    SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with SessionFactory() as session:
            source, target, incoming_source = _seed_enrollments(session)
            _seed_settlement_history(session, source.id, target.id, incoming_source.id)
            repo = IncomeRepository(session)

            components = repo.list_active_tuition_settlement_components(
                source.id,
                as_of_date=date(2026, 1, 3),
            )

            assert [item.kind for item in components] == [
                TuitionSettlementComponent.KIND_PAYMENT,
                TuitionSettlementComponent.KIND_REFUND,
                TuitionSettlementComponent.KIND_CREDIT_ADJUSTMENT,
            ]
            assert sum((item.amount for item in components), Decimal("0")) == Decimal("95")
            assert repo.sum_active_tuition_for_enrollment(
                source.id,
                as_of_date=date(2026, 1, 3),
            ) == Decimal("95")
    finally:
        engine.dispose()


def test_settlement_rows_preserve_repository_order_and_signed_amounts():
    components = (
        TuitionSettlementComponent(
            kind=TuitionSettlementComponent.KIND_PAYMENT,
            source=TuitionSettlementComponent.SOURCE_INCOME,
            source_id=7,
            effective_date=date(2026, 2, 1),
            amount=Decimal("100"),
            wallet="CASH",
            note="payment",
        ),
        TuitionSettlementComponent(
            kind=TuitionSettlementComponent.KIND_TRANSFER_OUT,
            source=TuitionSettlementComponent.SOURCE_TRANSFER,
            source_id=8,
            effective_date=date(2026, 2, 2),
            amount=Decimal("-25"),
            note="transfer",
            counterparty_enrollment_id=99,
        ),
    )

    rows = TuitionDetailService._settlement_rows(components)

    assert [row.source_id for row in rows] == [7, 8]
    assert [row.amount for row in rows] == [Decimal("100"), Decimal("-25")]
    assert rows[1].counterparty_enrollment_id == 99
    assert rows[0].reference == "INCOME #7"
