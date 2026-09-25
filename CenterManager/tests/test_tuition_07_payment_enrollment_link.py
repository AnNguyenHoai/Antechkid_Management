# -*- coding: utf-8 -*-
"""TUITION-07 — exact Enrollment attribution for Tuition payments."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest
from sqlalchemy.orm import sessionmaker

from centermanager.database.engine import create_engine_for_path
from centermanager.models.income import Income
from centermanager.repositories.income_repository import IncomeRepository
from centermanager.services.income_service import IncomeService, IncomeValidationError


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MIGRATION = PROJECT_ROOT / "migrations" / "versions" / "1e10a032_income_enrollment_attribution.py"
FORM_DIALOG = PROJECT_ROOT / "src" / "centermanager" / "ui" / "finance_workspace" / "income_form_dialog.py"
SERVICE_SOURCE = PROJECT_ROOT / "src" / "centermanager" / "services" / "income_service.py"


class _EnrollmentRepo:
    def __init__(self, enrollments):
        self._items = list(enrollments)

    def get_by_id(self, enrollment_id):
        return next((item for item in self._items if item.id == enrollment_id), None)

    def get_by_student_and_class(self, student_id, class_id):
        return [
            item
            for item in self._items
            if item.student_id == student_id and item.class_id == class_id
        ]


class _Provider:
    def __init__(self, enrollments):
        self._repo = _EnrollmentRepo(enrollments)

    def enrollments(self, _session):
        return self._repo


def _service_with(enrollments):
    service = IncomeService.__new__(IncomeService)
    service._repository_provider = _Provider(enrollments)
    return service


def _enrollment(enrollment_id, student_id=10, class_id=20):
    return SimpleNamespace(
        id=enrollment_id,
        student_id=student_id,
        class_id=class_id,
    )


def test_income_model_exposes_explicit_tuition_attribution_state():
    legacy = Income(income_type="Tuition")
    linked = Income(income_type="Tuition", enrollment_id=7)
    other = Income(income_type="Other")

    assert legacy.tuition_attribution_status == "UNRESOLVED_LEGACY"
    assert linked.tuition_attribution_status == "LINKED"
    assert other.tuition_attribution_status == "NOT_APPLICABLE"

    column = Income.__table__.c.enrollment_id
    assert column.nullable is True
    assert column.index is True
    foreign_key = next(iter(column.foreign_keys))
    assert foreign_key.target_fullname == "enrollments.id"
    assert foreign_key.ondelete == "RESTRICT"


def test_exact_enrollment_is_validated_against_student_and_class():
    service = _service_with([_enrollment(1), _enrollment(2, student_id=99)])

    resolved = service._resolve_tuition_enrollment(
        object(), student_id=10, class_id=20, enrollment_id=1
    )
    assert resolved.id == 1

    with pytest.raises(IncomeValidationError, match="does not belong"):
        service._resolve_tuition_enrollment(
            object(), student_id=10, class_id=20, enrollment_id=2
        )


def test_omitted_enrollment_auto_resolves_only_when_unambiguous():
    service = _service_with([_enrollment(1)])
    assert service._resolve_tuition_enrollment(
        object(), student_id=10, class_id=20, enrollment_id=None
    ).id == 1

    ambiguous = _service_with([_enrollment(1), _enrollment(2)])
    with pytest.raises(IncomeValidationError, match="Multiple Enrollment"):
        ambiguous._resolve_tuition_enrollment(
            object(), student_id=10, class_id=20, enrollment_id=None
        )

    missing = _service_with([])
    with pytest.raises(IncomeValidationError, match="No Enrollment contract"):
        missing._resolve_tuition_enrollment(
            object(), student_id=10, class_id=20, enrollment_id=None
        )


def test_non_tuition_cannot_carry_enrollment_identity():
    service = IncomeService.__new__(IncomeService)
    with pytest.raises(IncomeValidationError, match="only valid for Tuition"):
        service._validate_income_ownership("Book", 10, 20, enrollment_id=1)


def test_resolver_contract_is_independent_of_payment_date():
    source = SERVICE_SOURCE.read_text(encoding="utf-8")
    start = source.index("def _resolve_tuition_enrollment")
    end = source.index("def _resolve_finance_period", start)
    resolver = source[start:end]

    assert "payment_date" not in resolver
    assert "get_by_student_and_class" in resolver
    assert "Multiple Enrollment contracts" in resolver


def test_repository_paid_total_is_enrollment_scoped_and_excludes_voided(test_db_path):
    engine = create_engine_for_path(test_db_path)
    SessionLocal = sessionmaker(bind=engine)
    try:
        with SessionLocal() as session:
            session.add_all(
                [
                    Income(
                        enrollment_id=101,
                        amount=300000,
                        income_type="Tuition",
                        payment_method="CASH",
                        payment_date=date(2026, 1, 1),
                        status=Income.STATUS_ACTIVE,
                    ),
                    Income(
                        enrollment_id=101,
                        amount=200000,
                        income_type="Tuition",
                        payment_method="BANK",
                        payment_date=date(2026, 1, 15),
                        status=Income.STATUS_ACTIVE,
                    ),
                    Income(
                        enrollment_id=101,
                        amount=900000,
                        income_type="Tuition",
                        payment_method="CASH",
                        payment_date=date(2026, 1, 10),
                        status=Income.STATUS_VOIDED,
                    ),
                    Income(
                        enrollment_id=202,
                        amount=800000,
                        income_type="Tuition",
                        payment_method="CASH",
                        payment_date=date(2026, 1, 5),
                        status=Income.STATUS_ACTIVE,
                    ),
                    Income(
                        enrollment_id=None,
                        amount=700000,
                        income_type="Tuition",
                        payment_method="CASH",
                        payment_date=date(2026, 1, 8),
                        status=Income.STATUS_ACTIVE,
                    ),
                ]
            )
            session.commit()
            repo = IncomeRepository(session)

            assert repo.sum_active_tuition_for_enrollment(101) == Decimal("500000.0")
            assert repo.sum_active_tuition_for_enrollment(
                101, as_of_date=date(2026, 1, 10)
            ) == Decimal("300000.0")

            unresolved = repo.list_unattributed_tuition()
            assert len(unresolved) == 1
            assert unresolved[0].amount == 700000
            assert unresolved[0].tuition_attribution_status == "UNRESOLVED_LEGACY"
    finally:
        engine.dispose()


def test_migration_keeps_historical_rows_null_and_does_not_guess_backfill():
    source = MIGRATION.read_text(encoding="utf-8")
    assert 'revision = "1e10a032"' in source
    assert 'down_revision = "1e10a031"' in source
    assert 'sa.Column("enrollment_id", sa.Integer(), nullable=True)' in source
    assert 'ondelete="RESTRICT"' in source
    assert '"ix_incomes_enrollment_id"' in source
    assert "UPDATE incomes" not in source.upper()
    assert "backfill" in source.lower()


def test_income_ui_requires_exact_enrollment_for_tuition_and_not_payment_date_lookup():
    source = FORM_DIALOG.read_text(encoding="utf-8")
    assert "Enrollment học phí *" in source
    assert "list_tuition_enrollments" in source
    assert "— Chọn đúng Enrollment —" in source
    assert "Vui lòng chọn đúng Enrollment cho khoản học phí." in source
    assert "enrollment_id=enrollment_id" in source

    reload_start = source.index("def _reload_enrollments")
    reload_end = source.index("def _lock_identity_fields", reload_start)
    reload_source = source[reload_start:reload_end]
    assert "payment_date" not in reload_source
