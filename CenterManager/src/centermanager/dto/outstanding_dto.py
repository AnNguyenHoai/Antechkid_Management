# -*- coding: utf-8 -*-
"""Outstanding DTO for Enrollment-centric tuition balances."""
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

BALANCE_STATE_OWED = "OWED"
BALANCE_STATE_PAID = "PAID"
BALANCE_STATE_PREPAID = "PREPAID"
BALANCE_STATE_NO_TUITION_CONFIGURED = "NO_TUITION_CONFIGURED"

# Compatibility labels retained for older UI/tests while balance_state is the
# canonical tuition semantic introduced by TUITION-09.
OUTSTANDING_STATUS_PAID = "Paid"
OUTSTANDING_STATUS_PARTIAL = "Partial"
OUTSTANDING_STATUS_OVERPAID = "Overpaid"
OUTSTANDING_STATUS_NOT_YET = "Not Yet"
OUTSTANDING_STATUS_NO_TUITION_CONFIGURED = "No Tuition Configured"


@dataclass
class OutstandingDTO:
    student_id: int
    student_name: str
    student_code: str
    class_id: int
    class_name: str
    expected_tuition: int
    paid: int
    outstanding: int
    status: str
    tuition_configured: bool = True
    period_start: date | None = None
    period_end: date | None = None
    course_name: str | None = None
    enrollment_id: int | None = None
    balance_state: str = BALANCE_STATE_PAID

    @property
    def debt_amount(self):
        """Positive receivable amount; prepaid credit never offsets debt KPI."""
        return max(self.outstanding, 0)

    @property
    def prepaid_amount(self):
        """Positive credit amount while preserving signed outstanding balance."""
        return max(-self.outstanding, 0)

    @classmethod
    def create(
        cls,
        student_id: int,
        student_name: str,
        student_code: str,
        class_id: int,
        class_name: str,
        expected_tuition: int,
        paid: int,
        tuition_configured: bool = True,
        period_start: date | None = None,
        period_end: date | None = None,
        course_name: str | None = None,
        enrollment_id: int | None = None,
    ) -> "OutstandingDTO":
        outstanding = expected_tuition - paid

        if not tuition_configured:
            balance_state = BALANCE_STATE_NO_TUITION_CONFIGURED
            status = OUTSTANDING_STATUS_NO_TUITION_CONFIGURED
        elif outstanding > 0:
            balance_state = BALANCE_STATE_OWED
            status = (
                OUTSTANDING_STATUS_NOT_YET
                if paid == 0
                else OUTSTANDING_STATUS_PARTIAL
            )
        elif outstanding == 0:
            balance_state = BALANCE_STATE_PAID
            status = OUTSTANDING_STATUS_PAID
        else:
            balance_state = BALANCE_STATE_PREPAID
            status = OUTSTANDING_STATUS_OVERPAID

        return cls(
            student_id=student_id,
            student_name=student_name,
            student_code=student_code,
            class_id=class_id,
            class_name=class_name,
            expected_tuition=expected_tuition,
            paid=paid,
            outstanding=outstanding,
            status=status,
            tuition_configured=tuition_configured,
            period_start=period_start,
            period_end=period_end,
            course_name=course_name,
            enrollment_id=enrollment_id,
            balance_state=balance_state,
        )


@dataclass
class StudentOutstandingSummary:
    student_id: int
    student_name: str
    student_code: str
    total_expected: int
    total_paid: int
    total_outstanding: int
    status: str
    details: list[OutstandingDTO]
    has_unconfigured_tuition: bool = False
    balance_state: str = BALANCE_STATE_PAID

    @property
    def debt_amount(self):
        return max(self.total_outstanding, 0)

    @property
    def prepaid_amount(self):
        return max(-self.total_outstanding, 0)
