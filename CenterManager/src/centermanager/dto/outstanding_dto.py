# -*- coding: utf-8 -*-
"""
Outstanding DTO for tuition balance calculation.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class OutstandingDTO:
    student_id: int
    student_name: str
    student_code: str
    class_id: int
    class_name: str
    expected_tuition: int  # in VND
    paid: int              # in VND
    outstanding: int       # in VND (expected - paid)
    status: str            # "Paid", "Partial", "Overpaid"

    @classmethod
    def create(
        cls,
        student_id: int,
        student_name: str,
        student_code: str,
        class_id: int,
        class_name: str,
        expected_tuition: int,
        paid: int
    ) -> "OutstandingDTO":
        outstanding = expected_tuition - paid
        if outstanding == 0:
            status = "Paid"
        elif outstanding > 0:
            status = "Partial"
        else:
            status = "Overpaid"
        return cls(
            student_id=student_id,
            student_name=student_name,
            student_code=student_code,
            class_id=class_id,
            class_name=class_name,
            expected_tuition=expected_tuition,
            paid=paid,
            outstanding=outstanding,
            status=status
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
    details: list[OutstandingDTO]  # per class details