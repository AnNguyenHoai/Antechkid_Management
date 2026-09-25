"""Canonical, versioned tuition billing policy for teaching sessions."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, List, Mapping, Optional

from centermanager.models.attendance import AttendanceStatus
from centermanager.models.session import SessionStatus


LEGACY_SESSION_ONLY_POLICY = "legacy_session_only_v1"
ATTENDANCE_AWARE_POLICY_V1 = "attendance_v1"
CURRENT_BILLING_POLICY_VERSION = ATTENDANCE_AWARE_POLICY_V1
SUPPORTED_BILLING_POLICY_VERSIONS = frozenset(
    {LEGACY_SESSION_ONLY_POLICY, ATTENDANCE_AWARE_POLICY_V1}
)


@dataclass(frozen=True)
class BillableSessionDecision:
    billable: bool
    reason: str
    attendance_status: Optional[str] = None
    policy_version: str = LEGACY_SESSION_ONLY_POLICY


class BillableSessionPolicy:
    """Single source of truth for Enrollment session billability."""

    REASON_BILLABLE = "completed_in_effective_range"
    REASON_NOT_COMPLETED = "session_not_completed"
    REASON_UNRESOLVED_RANGE = "enrollment_range_unresolved"
    REASON_OUTSIDE_RANGE = "outside_enrollment_range"
    REASON_CLASS_MISMATCH = "class_mismatch"
    REASON_INVALID_SESSION_NUMBER = "invalid_session_number"
    REASON_ENROLLMENT_FROZEN = "enrollment_frozen_for_session"
    REASON_ATTENDANCE_PRESENT = "attendance_present"
    REASON_ATTENDANCE_LATE = "attendance_late"
    REASON_ATTENDANCE_ABSENT = "attendance_absent_reserved_session"
    REASON_ATTENDANCE_MISSING = "attendance_missing_fallback_billable"
    REASON_ATTENDANCE_EXCUSED = "attendance_excused_waiver"
    REASON_ATTENDANCE_UNKNOWN = "attendance_status_unrecognized"
    REASON_UNSUPPORTED_POLICY = "unsupported_billing_policy_version"

    @staticmethod
    def policy_version_for(enrollment) -> str:
        return getattr(enrollment, "billing_policy_version", None) or LEGACY_SESSION_ONLY_POLICY

    @classmethod
    def _session_gate(cls, session, enrollment) -> Optional[BillableSessionDecision]:
        version = cls.policy_version_for(enrollment)
        if getattr(session, "status", None) != SessionStatus.COMPLETED.value:
            return BillableSessionDecision(False, cls.REASON_NOT_COMPLETED, policy_version=version)
        session_number = getattr(session, "session_number", None)
        if session_number is None or int(session_number) < 1:
            return BillableSessionDecision(False, cls.REASON_INVALID_SESSION_NUMBER, policy_version=version)
        enrolled_from = getattr(enrollment, "enrolled_from_session", None)
        enrolled_until = getattr(enrollment, "enrolled_until_session", None)
        if enrolled_from is None or enrolled_until is None:
            return BillableSessionDecision(False, cls.REASON_UNRESOLVED_RANGE, policy_version=version)
        session_class_id = getattr(session, "class_id", None)
        enrollment_class_id = getattr(enrollment, "class_id", None)
        if session_class_id is not None and enrollment_class_id is not None and session_class_id != enrollment_class_id:
            return BillableSessionDecision(False, cls.REASON_CLASS_MISMATCH, policy_version=version)
        if not int(enrolled_from) <= int(session_number) <= int(enrolled_until):
            return BillableSessionDecision(False, cls.REASON_OUTSIDE_RANGE, policy_version=version)
        for freeze in (getattr(enrollment, "freezes", None) or []):
            start = getattr(freeze, "start_session", None)
            end = getattr(freeze, "end_session", None)
            if start is not None and int(session_number) >= int(start) and (end is None or int(session_number) <= int(end)):
                return BillableSessionDecision(False, cls.REASON_ENROLLMENT_FROZEN, policy_version=version)
        return None

    @staticmethod
    def _attendance_status(attendance) -> Optional[str]:
        if attendance is None:
            return None
        if isinstance(attendance, str):
            return attendance
        return getattr(attendance, "status", None)

    @classmethod
    def evaluate(cls, session, enrollment, attendance=None) -> BillableSessionDecision:
        gate_decision = cls._session_gate(session, enrollment)
        if gate_decision is not None:
            return gate_decision
        version = cls.policy_version_for(enrollment)
        if version == LEGACY_SESSION_ONLY_POLICY:
            return BillableSessionDecision(True, cls.REASON_BILLABLE, cls._attendance_status(attendance), version)
        if version != ATTENDANCE_AWARE_POLICY_V1:
            return BillableSessionDecision(False, cls.REASON_UNSUPPORTED_POLICY, cls._attendance_status(attendance), version)
        status = cls._attendance_status(attendance)
        if status is None:
            return BillableSessionDecision(True, cls.REASON_ATTENDANCE_MISSING, policy_version=version)
        if status == AttendanceStatus.PRESENT.value:
            return BillableSessionDecision(True, cls.REASON_ATTENDANCE_PRESENT, status, version)
        if status == AttendanceStatus.LATE.value:
            return BillableSessionDecision(True, cls.REASON_ATTENDANCE_LATE, status, version)
        if status == AttendanceStatus.ABSENT.value:
            return BillableSessionDecision(True, cls.REASON_ATTENDANCE_ABSENT, status, version)
        if status == AttendanceStatus.EXCUSED.value:
            return BillableSessionDecision(False, cls.REASON_ATTENDANCE_EXCUSED, status, version)
        return BillableSessionDecision(False, cls.REASON_ATTENDANCE_UNKNOWN, status, version)

    @classmethod
    def is_billable(cls, session, enrollment, attendance=None) -> bool:
        return cls.evaluate(session, enrollment, attendance).billable

    @classmethod
    def filter_billable(cls, sessions: Iterable, enrollment, attendance_by_session_id: Optional[Mapping[int, object]] = None) -> List:
        attendance_by_session_id = attendance_by_session_id or {}
        return [session for session in sessions if cls.is_billable(session, enrollment, attendance_by_session_id.get(getattr(session, "id", None)))]
