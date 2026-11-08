"""Schema contract: V1 is opt-in and preserves legacy Enrollment/Income columns."""
from sqlalchemy import create_engine, inspect

from centermanager.database.base import Base
from centermanager import models  # noqa: F401
from centermanager.models.enrollment import Enrollment
from centermanager.models.monthly_tuition import (
    EnrollmentMonthlyTuitionTerm,
    MonthlyTuitionAllocationRecord,
    MonthlyTuitionOutcomeRecord,
    MonthlyTuitionPlanRecord,
)


def test_monthly_tuition_schema_metadata_is_additive():
    expected = {
        "monthly_tuition_plans", "monthly_tuition_allocations",
        "enrollment_monthly_tuition_terms", "monthly_tuition_outcomes",
    }
    assert expected <= set(Base.metadata.tables)
    assert Enrollment.__table__.name == "enrollments"
    assert "billing_policy_version" in Enrollment.__table__.columns
    for obj in (MonthlyTuitionPlanRecord, MonthlyTuitionAllocationRecord,
                EnrollmentMonthlyTuitionTerm, MonthlyTuitionOutcomeRecord):
        assert obj.__table__.name in expected


def test_monthly_tuition_schema_creates_in_temporary_sqlite():
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    names = set(inspect(engine).get_table_names())
    assert {
        "monthly_tuition_plans", "monthly_tuition_allocations",
        "enrollment_monthly_tuition_terms", "monthly_tuition_outcomes",
    } <= names
    assert "enrollments" in names and "incomes" in names
    engine.dispose()

def test_admin_reset_never_deletes_monthly_tuition_evidence():
    from centermanager.repositories.admin_data_reset_repository import AdminDataResetRepository
    protected = AdminDataResetRepository.PROTECTED_TABLES
    assert {
        "monthly_tuition_plans",
        "monthly_tuition_allocations",
        "enrollment_monthly_tuition_terms",
        "monthly_tuition_outcomes",
    } <= set(protected)
