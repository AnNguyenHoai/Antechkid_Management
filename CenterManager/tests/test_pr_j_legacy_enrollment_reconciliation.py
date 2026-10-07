# -*- coding: utf-8 -*-
"""PR J — legacy Enrollment duplicate reconciliation regression coverage."""
from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.models.session import SessionStatus
from centermanager.services.enrollment_reconciliation_service import (
    EnrollmentReconciliationService,
    EnrollmentReconciliationValidationError,
)


ROOT = Path(__file__).resolve().parents[1]


class _SessionContext:
    def __init__(self):
        self.commits = 0

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def commit(self):
        self.commits += 1


class _EnrollmentRepo:
    def __init__(self, rows):
        self.rows = list(rows)

    def get_by_id(self, enrollment_id):
        return next((row for row in self.rows if row.id == enrollment_id), None)

    def get_by_class_with_student_including_reconciled(self, class_id):
        return [row for row in self.rows if row.class_id == class_id]


class _SessionsRepo:
    def __init__(self, rows):
        self.rows = list(rows)

    def get_by_class(self, class_id):
        return [row for row in self.rows if row.class_id == class_id]


class _IncomeRepo:
    def __init__(self, rows):
        self.rows = list(rows)

    def list_tuition_for_enrollment_including_history(self, enrollment_id):
        return [row for row in self.rows if row.enrollment_id == enrollment_id]

    def reattribute_tuition_enrollment(self, source_enrollment_id, target_enrollment_id):
        moved = []
        for row in self.rows:
            if row.enrollment_id == source_enrollment_id:
                row.enrollment_id = target_enrollment_id
                moved.append(row.id)
        return moved


class _FreezeRepo:
    def __init__(self, blocked=False):
        self.blocked = blocked

    def list_for_enrollment(self, _enrollment_id):
        return [SimpleNamespace(id=1)] if self.blocked else []


class _AdjustmentRepo:
    def __init__(self, blocked=False):
        self.blocked = blocked

    def has_for_enrollment(self, _enrollment_id):
        return self.blocked


class _TransferRepo:
    def __init__(self, blocked=False):
        self.blocked = blocked

    def has_for_enrollment(self, _enrollment_id):
        return self.blocked


class _Provider:
    def __init__(self, enrollments, sessions, incomes, *, blocker=None):
        self.enrollment_repo = _EnrollmentRepo(enrollments)
        self.session_repo = _SessionsRepo(sessions)
        self.income_repo = _IncomeRepo(incomes)
        self.freeze_repo = _FreezeRepo(blocker == "freeze")
        self.adjustment_repo = _AdjustmentRepo(blocker == "adjustment")
        self.transfer_repo = _TransferRepo(blocker == "transfer")

    def enrollments(self, _session):
        return self.enrollment_repo

    def sessions(self, _session):
        return self.session_repo

    def incomes(self, _session):
        return self.income_repo

    def enrollment_freezes(self, _session):
        return self.freeze_repo

    def tuition_adjustments(self, _session):
        return self.adjustment_repo

    def enrollment_transfers(self, _session):
        return self.transfer_repo


class _Audit:
    def __init__(self):
        self.calls = []

    def record_in_session(self, _session, **kwargs):
        self.calls.append(kwargs)


def _session(number, on_date):
    return SimpleNamespace(
        id=number,
        class_id=20,
        session_number=number,
        status=SessionStatus.COMPLETED.value,
        scheduled_date=on_date,
        actual_date=on_date,
    )


def _enrollment(
    enrollment_id,
    status,
    *,
    ended_on=None,
    start=1,
    end=10,
    reviewed=False,
):
    return SimpleNamespace(
        id=enrollment_id,
        student_id=10,
        class_id=20,
        class_name="K1_Python",
        status=status,
        enrolled_from_session=start,
        enrolled_until_session=end,
        end_date=ended_on,
        reconciled_into_enrollment_id=None,
        reconciled_at=None,
        reconciled_by=None,
        reconcile_reason=None,
        reconciliation_reviewed_at=date(2026, 1, 1) if reviewed else None,
        reconciliation_reviewed_by=None,
        reconciliation_review_reason=None,
        student=SimpleNamespace(id=10, full_name="Gia Hào"),
    )


def _income(income_id, enrollment_id, amount=87500):
    return SimpleNamespace(
        id=income_id,
        enrollment_id=enrollment_id,
        amount=amount,
        status="ACTIVE",
        deleted_at=None,
    )


def _service(*, blocker=None, reviewed=False):
    canonical = _enrollment(202, "ACTIVE", start=1, end=10)
    duplicate = _enrollment(
        101,
        "WITHDRAWN",
        ended_on=date(2026, 1, 12),
        start=1,
        end=10,
        reviewed=reviewed,
    )
    sessions = [
        _session(1, date(2026, 1, 5)),
        _session(2, date(2026, 1, 12)),
        _session(3, date(2026, 1, 19)),
    ]
    incomes = [_income(1, 101), _income(2, 202, 175000)]
    provider = _Provider([duplicate, canonical], sessions, incomes, blocker=blocker)
    audit = _Audit()
    sessions_created = []

    def session_factory():
        session = _SessionContext()
        sessions_created.append(session)
        return session

    service = EnrollmentReconciliationService(
        session_factory,
        provider,
        audit_service=audit,
    )
    return service, provider, audit, duplicate, canonical, sessions_created


def test_candidate_detects_withdrawn_contract_covered_by_active_contract():
    service, _provider, _audit, _duplicate, _canonical, _sessions = _service()

    candidates = service.find_candidates(20)

    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.duplicate_enrollment_id == 101
    assert candidate.canonical_enrollment_id == 202
    assert candidate.duplicate_effective_range == (1, 2)
    assert candidate.canonical_range == (1, 10)
    assert candidate.tuition_income_count == 1
    assert candidate.tuition_income_total == Decimal("87500")
    assert candidate.blockers == ()


def test_reconcile_moves_tuition_attribution_and_keeps_duplicate_as_lineage_history():
    service, provider, audit, duplicate, _canonical, sessions_created = _service()

    moved = service.reconcile(101, 202, reason="Accidental remove/add")

    assert moved == [1]
    assert provider.income_repo.rows[0].enrollment_id == 202
    assert duplicate.reconciled_into_enrollment_id == 202
    assert duplicate.reconcile_reason == "Accidental remove/add"
    assert duplicate.status == "WITHDRAWN"
    assert sessions_created[-1].commits == 1
    assert audit.calls[-1]["action"] == "ENROLLMENT_RECONCILED"
    assert audit.calls[-1]["details"]["moved_tuition_income_ids"] == [1]


@pytest.mark.parametrize(
    ("blocker", "expected"),
    [
        ("freeze", "TUITION_FREEZE_HISTORY"),
        ("adjustment", "TUITION_ADJUSTMENT_LEDGER"),
        ("transfer", "ENROLLMENT_TRANSFER_LEDGER"),
    ],
)
def test_immutable_history_blocks_automatic_reconciliation(blocker, expected):
    service, _provider, _audit, _duplicate, _canonical, _sessions = _service(
        blocker=blocker
    )

    candidate = service.find_candidates(20)[0]
    assert expected in candidate.blockers

    with pytest.raises(
        EnrollmentReconciliationValidationError,
        match="blocked by immutable history",
    ):
        service.reconcile(101, 202, reason="Accidental remove/add")


def test_mark_legitimate_removes_candidate_without_deleting_history():
    service, _provider, audit, duplicate, _canonical, sessions_created = _service()

    service.mark_legitimate(101, reason="Student genuinely returned later")

    assert duplicate.reconciliation_reviewed_at is not None
    assert duplicate.reconciliation_review_reason == "Student genuinely returned later"
    assert service.find_candidates(20) == []
    assert sessions_created[0].commits == 1
    assert audit.calls[-1]["action"] == "ENROLLMENT_RECONCILIATION_REVIEWED_LEGITIMATE"


def test_repository_operational_queries_exclude_reconciled_rows():
    source = (
        ROOT / "src/centermanager/repositories/enrollment_repository.py"
    ).read_text(encoding="utf-8")

    assert "Enrollment.reconciled_into_enrollment_id.is_(None)" in source
    assert "get_by_student_and_class_including_reconciled" in source
    assert "get_by_class_with_student_including_reconciled" in source


def test_reconciliation_never_hard_deletes_enrollment_or_rewrites_immutable_ledgers():
    source = (
        ROOT / "src/centermanager/services/enrollment_reconciliation_service.py"
    ).read_text(encoding="utf-8")

    assert ".delete(" not in source
    assert "reattribute_tuition_enrollment" in source
    assert "TUITION_ADJUSTMENT_LEDGER" in source
    assert "ENROLLMENT_TRANSFER_LEDGER" in source
    assert "TUITION_FREEZE_HISTORY" in source
    assert "session.query" not in source


def test_migration_adds_lineage_without_guessing_or_backfilling_history():
    migration = (
        ROOT
        / "migrations/versions/1e10a040_enrollment_reconciliation_lineage.py"
    ).read_text(encoding="utf-8")

    assert 'revision = "1e10a040"' in migration
    assert 'down_revision = "1e10a039"' in migration
    assert '"reconciled_into_enrollment_id"' in migration
    assert '"reconciliation_reviewed_at"' in migration
    assert "UPDATE enrollments" not in migration
    assert "INSERT INTO" not in migration


def test_class_ui_requires_explicit_reconcile_or_keep_separate_decision():
    source = (
        ROOT / "src/centermanager/ui/class_workspace/class_enrollment_dialog.py"
    ).read_text(encoding="utf-8")

    assert '"Repair legacy duplicates"' in source
    assert '"Reconcile into active"' in source
    assert '"Keep separate"' in source
    assert "reconcile_legacy_enrollment_duplicate(" in source
    assert "mark_legacy_enrollment_legitimate(" in source


def test_student_history_surfaces_reconciled_lineage():
    source = (
        ROOT / "src/centermanager/ui/student_workspace/enrollment_widget.py"
    ).read_text(encoding="utf-8")

    assert "Reconciled into Enrollment #" in source
