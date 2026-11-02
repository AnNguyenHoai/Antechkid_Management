"""QA-S03: Tuition receipt attribution and historical as-of separation.

Real ORM/repository with disposable SQLCipher-capable test engine, no production
data. Verify Finance invariants I05/I06 without assuming a calendar period is a
tuition contract or assigning legacy income to an enrollment.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy.orm import sessionmaker

from centermanager.database.engine import create_engine_for_path
from centermanager.models.class_ import Class
from centermanager.models.enrollment import Enrollment
from centermanager.models.income import Income
from centermanager.models.student import Student
from centermanager.repositories.income_repository import IncomeRepository


def test_tuition_receipts_stay_on_exact_enrollment_and_respect_as_of(test_db_path):
    engine = create_engine_for_path(test_db_path)
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    try:
        with Session() as session:
            student = Student(student_code="QA-S03-001", full_name="QA tuition student")
            class_old = Class(name="QA old class")
            class_new = Class(name="QA new class")
            session.add_all([student, class_old, class_new])
            session.flush()
            old = Enrollment(student_id=student.id, class_id=class_old.id, class_name=class_old.name)
            new = Enrollment(student_id=student.id, class_id=class_new.id, class_name=class_new.name)
            session.add_all([old, new])
            session.flush()
            session.add_all([
                Income(enrollment_id=old.id, student_id=student.id, amount=100,
                       income_type="Tuition", payment_method="BANK",
                       payment_date=date(2026, 1, 5), status=Income.STATUS_ACTIVE),
                Income(enrollment_id=old.id, student_id=student.id, amount=40,
                       income_type="Tuition", payment_method="CASH",
                       payment_date=date(2026, 3, 5), status=Income.STATUS_ACTIVE),
                Income(enrollment_id=new.id, student_id=student.id, amount=70,
                       income_type="Tuition", payment_method="BANK",
                       payment_date=date(2026, 2, 5), status=Income.STATUS_ACTIVE),
                Income(enrollment_id=old.id, student_id=student.id, amount=900,
                       income_type="Other", payment_method="BANK",
                       payment_date=date(2026, 1, 6), status=Income.STATUS_ACTIVE),
                Income(enrollment_id=old.id, student_id=student.id, amount=500,
                       income_type="Tuition", payment_method="BANK",
                       payment_date=date(2026, 1, 7), status=Income.STATUS_VOIDED),
                Income(enrollment_id=None, student_id=student.id, amount=1000,
                       income_type="Tuition", payment_method="BANK",
                       payment_date=date(2026, 1, 8), status=Income.STATUS_ACTIVE),
            ])
            session.commit()
            repository = IncomeRepository(session)
            assert repository.sum_active_tuition_for_enrollment(
                old.id, as_of_date=date(2026, 2, 28)
            ) == Decimal("100")
            assert repository.sum_active_tuition_for_enrollment(
                old.id, as_of_date=date(2026, 3, 31)
            ) == Decimal("140")
            assert repository.sum_active_tuition_for_enrollment(
                new.id, as_of_date=date(2026, 3, 31)
            ) == Decimal("70")
    finally:
        engine.dispose()
