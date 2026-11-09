"""Repository-owned SQLAlchemy boundary for opt-in monthly tuition commands.

This adapter owns all queries, flush/add and data access. Application services
validate policy, permissions, finish SQLCipher transactions and record recovery.
"""
from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from centermanager.models.enrollment import Enrollment
from centermanager.models.income import Income
from centermanager.models.monthly_tuition import (
    EnrollmentMonthlyTuitionTerm, MonthlyTuitionAllocationRecord,
    MonthlyTuitionOutcomeRecord, MonthlyTuitionPlanRecord,
)
from centermanager.models.session import Session as TeachingSession


class MonthlyTuitionRepository:
    def __init__(self, session: Session):
        self._session = session

    def enrollment(self, enrollment_id: int):
        return self._session.get(Enrollment, enrollment_id)

    def teaching_session(self, session_id: int):
        return self._session.get(TeachingSession, session_id)

    def term(self, enrollment_id: int):
        return self._session.scalars(select(EnrollmentMonthlyTuitionTerm).where(
            EnrollmentMonthlyTuitionTerm.enrollment_id == enrollment_id
        )).first()

    def unattributed_tuition_receipt(self, student_id: int, class_id: int) -> bool:
        return self._session.scalars(select(Income.id).where(
            Income.student_id == student_id,
            Income.class_id == class_id,
            Income.income_type == "Tuition",
            Income.enrollment_id.is_(None),
            Income.status == Income.STATUS_ACTIVE,
            Income.deleted_at.is_(None),
        )).first() is not None

    def active_plan(self, class_id: int, month: date, *, allow_closed: bool = False):
        statuses = ("ACTIVE", "CLOSED") if allow_closed else ("ACTIVE",)
        plans = self._session.scalars(select(MonthlyTuitionPlanRecord).where(
            MonthlyTuitionPlanRecord.class_id == class_id,
            MonthlyTuitionPlanRecord.month == month,
            MonthlyTuitionPlanRecord.status.in_(statuses),
        )).all()
        if len(plans) > 1:
            raise ValueError("Ambiguous activated monthly tuition plans")
        return plans[0] if plans else None

    def allocation(self, plan_id: int, session_id: int):
        return self._session.scalars(select(MonthlyTuitionAllocationRecord).where(
            MonthlyTuitionAllocationRecord.plan_id == plan_id,
            MonthlyTuitionAllocationRecord.session_id == session_id,
        )).first()

    def replacement_already_allocated(self, session_id: int) -> bool:
        return self._session.scalars(select(MonthlyTuitionAllocationRecord.id).where(
            MonthlyTuitionAllocationRecord.session_id == session_id
        )).first() is not None

    def outcome_by_key(self, key: str):
        return self._session.scalars(select(MonthlyTuitionOutcomeRecord).where(
            MonthlyTuitionOutcomeRecord.idempotency_key == key
        )).first()

    def outcomes_for_session(self, enrollment_id: int, session_id: int):
        return self._session.scalars(select(MonthlyTuitionOutcomeRecord).where(
            MonthlyTuitionOutcomeRecord.enrollment_id == enrollment_id,
            MonthlyTuitionOutcomeRecord.session_id == session_id,
        )).all()

    def create_term(self, *, enrollment_id: int, effective_from: date,
                    actor_name: str, activated_at: datetime):
        term = EnrollmentMonthlyTuitionTerm(
            enrollment_id=enrollment_id, effective_from=effective_from,
            activated_at=activated_at, activated_by=actor_name,
        )
        self._session.add(term)
        self._session.flush()
        return term

    def create_outcome(self, *, enrollment_id: int, session_id: int,
                       outcome: str, revision: int, replacement_session_id: int | None,
                       reason: str, idempotency_key: str,
                       effective_date: date, recorded_at: datetime, recorded_by: str):
        event = MonthlyTuitionOutcomeRecord(
            enrollment_id=enrollment_id, session_id=session_id,
            outcome=outcome, revision=revision,
            replacement_session_id=replacement_session_id,
            reason=reason, idempotency_key=idempotency_key,
            effective_date=effective_date, recorded_at=recorded_at,
            recorded_by=recorded_by,
        )
        self._session.add(event)
        self._session.flush()
        return event
