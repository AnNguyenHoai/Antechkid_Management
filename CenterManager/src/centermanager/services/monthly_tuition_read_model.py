"""SQLAlchemy monthly tuition accrual resolver, scoped to an opt-in Enrollment.

No Income is posted here. Exact Enrollment cash receipts remain owned by
IncomeRepository. All historical legacy accrual precedes the explicit opt-in
date and is not reinterpreted.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from sqlalchemy import select, inspect
from sqlalchemy.orm import Session as SqlAlchemySession

from centermanager.models.monthly_tuition import (
    EnrollmentMonthlyTuitionTerm, MonthlyTuitionPlanRecord,
    MonthlyTuitionAllocationRecord, MonthlyTuitionOutcomeRecord,
)
from centermanager.models.session import Session, SessionStatus
from centermanager.services.tuition_accrual_service import (
    TuitionAccrualService, TuitionAccrualUnresolvedError,
)


@dataclass(frozen=True)
class MonthlyAccrualProjection:
    enrollment_id: int
    accrued_vnd: Decimal
    historical_legacy_vnd: Decimal
    historical_legacy_gross_vnd: Decimal
    historical_legacy_discount_vnd: Decimal
    legacy_billable_numbers: tuple[int, ...]
    monthly_vnd: Decimal
    monthly_gross_vnd: Decimal
    cancelled_vnd: Decimal
    monthly_contributions: tuple[tuple[int, Decimal], ...]


class MonthlyTuitionReadModel:
    """Resolve monthly terms without changing the legacy source of truth."""

    @staticmethod
    def has_monthly_term(db, enrollment_id: int) -> bool:
        if not isinstance(db, SqlAlchemySession):
            return False
        # Older isolated test databases may not have run additive Alembic yet.
        # The production database is migrated under the existing startup gate.
        key = "_monthly_tuition_terms_table_available"
        if key not in db.info:
            db.info[key] = inspect(db.get_bind()).has_table("enrollment_monthly_tuition_terms")
        if not db.info[key]:
            return False
        return db.scalars(select(EnrollmentMonthlyTuitionTerm).where(
            EnrollmentMonthlyTuitionTerm.enrollment_id == enrollment_id
        )).first() is not None

    @classmethod
    def project(cls, db, enrollment, sessions, as_of_date: date) -> MonthlyAccrualProjection:
        term = db.scalars(select(EnrollmentMonthlyTuitionTerm).where(
            EnrollmentMonthlyTuitionTerm.enrollment_id == enrollment.id
        )).first()
        if term is None:
            raise TuitionAccrualUnresolvedError("Enrollment has no activated monthly tuition term")
        if enrollment.class_id is None:
            raise TuitionAccrualUnresolvedError("Enrollment has no class")
        sessions = tuple(sessions)
        by_id = {int(s.id): s for s in sessions if s.id is not None}
        if not getattr(enrollment, "has_tuition_contract", False):
            raise TuitionAccrualUnresolvedError("Historical Enrollment tuition is unresolved")
        legacy_sessions = [s for s in sessions if s.scheduled_date < term.effective_from]
        legacy = TuitionAccrualService.calculate_from_records(
            enrollment, legacy_sessions, as_of_date
        )
        plans = db.scalars(select(MonthlyTuitionPlanRecord).where(
            MonthlyTuitionPlanRecord.class_id == enrollment.class_id,
            MonthlyTuitionPlanRecord.month >= term.effective_from.replace(day=1),
            MonthlyTuitionPlanRecord.month <= as_of_date.replace(day=1),
            MonthlyTuitionPlanRecord.status.in_(("ACTIVE", "CLOSED")),
        )).all()
        # Historical months may not be re-priced by a later version.
        by_month = {}
        for plan in plans:
            if plan.month in by_month:
                raise TuitionAccrualUnresolvedError("Multiple activated plans for one month")
            by_month[plan.month] = plan

        known_session_months = {
            s.scheduled_date.replace(day=1) for s in sessions
            if term.effective_from <= s.scheduled_date <= as_of_date
            and (term.effective_until is None or s.scheduled_date <= term.effective_until)
        }
        if known_session_months - set(by_month):
            raise TuitionAccrualUnresolvedError("Missing activated monthly tuition plan")

        # Outcomes are append-only and versioned; replay uses latest revision.
        outcome_rows = db.scalars(select(MonthlyTuitionOutcomeRecord).where(
            MonthlyTuitionOutcomeRecord.enrollment_id == enrollment.id
        )).all()
        latest = {}
        for event in outcome_rows:
            if event.recorded_at.date() > as_of_date:
                continue
            prior = latest.get(event.session_id)
            if prior is None or event.revision > prior.revision:
                latest[event.session_id] = event
            elif event.revision == prior.revision:
                raise TuitionAccrualUnresolvedError("Conflicting event revisions")
        gross, cancelled = 0, 0
        contributions = []
        for plan in by_month.values():
            allocations = db.scalars(select(MonthlyTuitionAllocationRecord).where(
                MonthlyTuitionAllocationRecord.plan_id == plan.id
            )).all()
            if not allocations or sum(row.amount_vnd for row in allocations) != plan.monthly_fee_vnd:
                raise TuitionAccrualUnresolvedError("Incomplete monthly allocation snapshot")
            for row in allocations:
                original_date = row.original_date
                if original_date > as_of_date or original_date < term.effective_from:
                    continue
                if term.effective_until is not None and original_date > term.effective_until:
                    continue
                if enrollment.end_date is not None and original_date > enrollment.end_date:
                    continue
                session = by_id.get(row.session_id)
                if session is None or session.class_id != enrollment.class_id:
                    raise TuitionAccrualUnresolvedError("Monthly plan references missing or foreign session")
                withdrawn = getattr(enrollment, "withdrawn_from_session", None)
                if withdrawn is not None and session.session_number >= withdrawn:
                    continue
                if row.original_date.replace(day=1) != plan.month:
                    raise TuitionAccrualUnresolvedError("Session allocation month mismatch")
                outcome = latest.get(row.session_id)
                if session.status == SessionStatus.CANCELLED.value and outcome is None:
                    raise TuitionAccrualUnresolvedError("Cancelled session has no approved billing outcome")
                gross += row.amount_vnd
                if outcome is not None and outcome.outcome == "CENTRE_CANCELLED_NO_MAKEUP":
                    cancelled += row.amount_vnd
                else:
                    contributions.append((row.session_id, Decimal(row.amount_vnd)))
        monthly = Decimal(gross - cancelled)
        return MonthlyAccrualProjection(
            enrollment_id=int(enrollment.id),
            accrued_vnd=Decimal(legacy.net_accrued) + monthly,
            historical_legacy_vnd=Decimal(legacy.net_accrued),
            historical_legacy_gross_vnd=Decimal(legacy.gross_accrued),
            historical_legacy_discount_vnd=Decimal(legacy.discount),
            legacy_billable_numbers=legacy.billable_session_numbers,
            monthly_vnd=monthly,
            monthly_gross_vnd=Decimal(gross),
            cancelled_vnd=Decimal(cancelled),
            monthly_contributions=tuple(sorted(contributions)),
        )
