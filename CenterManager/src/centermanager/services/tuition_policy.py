"""Canonical phase-1 tuition billing policy for teaching sessions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List

from centermanager.models.session import SessionStatus


@dataclass(frozen=True)
class BillableSessionDecision:
    """Deterministic decision for whether one session accrues tuition."""

    billable: bool
    reason: str


class BillableSessionPolicy:
    """Single source of truth for phase-1 session billability.

    Policy:
    - only COMPLETED sessions are billable;
    - session number must fall inside the Enrollment's inclusive effective
      session range;
    - when both aggregates expose a class id, they must refer to the same class;
    - unresolved historical Enrollments are not billable until their effective
      session range is known;
    - Attendance is intentionally outside this phase-1 policy.

    This policy belongs only to the academic/tuition domain. Accounting-period
    selection does not participate in the decision.
    """

    REASON_BILLABLE = "completed_in_effective_range"
    REASON_NOT_COMPLETED = "session_not_completed"
    REASON_UNRESOLVED_RANGE = "enrollment_range_unresolved"
    REASON_OUTSIDE_RANGE = "outside_enrollment_range"
    REASON_CLASS_MISMATCH = "class_mismatch"
    REASON_INVALID_SESSION_NUMBER = "invalid_session_number"

    @classmethod
    def evaluate(cls, session, enrollment) -> BillableSessionDecision:
        if getattr(session, "status", None) != SessionStatus.COMPLETED.value:
            return BillableSessionDecision(False, cls.REASON_NOT_COMPLETED)

        session_number = getattr(session, "session_number", None)
        if session_number is None or int(session_number) < 1:
            return BillableSessionDecision(False, cls.REASON_INVALID_SESSION_NUMBER)

        enrolled_from = getattr(enrollment, "enrolled_from_session", None)
        enrolled_until = getattr(enrollment, "enrolled_until_session", None)
        if enrolled_from is None or enrolled_until is None:
            return BillableSessionDecision(False, cls.REASON_UNRESOLVED_RANGE)

        session_class_id = getattr(session, "class_id", None)
        enrollment_class_id = getattr(enrollment, "class_id", None)
        if (
            session_class_id is not None
            and enrollment_class_id is not None
            and session_class_id != enrollment_class_id
        ):
            return BillableSessionDecision(False, cls.REASON_CLASS_MISMATCH)

        if not int(enrolled_from) <= int(session_number) <= int(enrolled_until):
            return BillableSessionDecision(False, cls.REASON_OUTSIDE_RANGE)

        return BillableSessionDecision(True, cls.REASON_BILLABLE)

    @classmethod
    def is_billable(cls, session, enrollment) -> bool:
        return cls.evaluate(session, enrollment).billable

    @classmethod
    def filter_billable(cls, sessions: Iterable, enrollment) -> List:
        """Return billable sessions while preserving caller-provided order."""
        return [session for session in sessions if cls.is_billable(session, enrollment)]
