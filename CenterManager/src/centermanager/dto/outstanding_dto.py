# -*- coding: utf-8 -*-
"""
Outstanding DTO for tuition balance calculation.
"""
from dataclasses import dataclass
from typing import Optional

OUTSTANDING_STATUS_PAID = "Paid"
OUTSTANDING_STATUS_PARTIAL = "Partial"
OUTSTANDING_STATUS_OVERPAID = "Overpaid"
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
    ) -> "OutstandingDTO":
        outstanding = expected_tuition - paid

        if not tuition_configured:
            status = OUTSTANDING_STATUS_NO_TUITION_CONFIGURED
        elif outstanding == 0:
            status = OUTSTANDING_STATUS_PAID
        elif outstanding > 0:
            status = OUTSTANDING_STATUS_PARTIAL
        else:
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
