"""Read-only finance diagnostics projections; amounts are evidence, not corrections."""
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Optional


@dataclass(frozen=True)
class FinanceFinding:
    rule_id: str
    source_version: str
    as_of_date: date
    detected_at: datetime
    severity: str
    entity_type: str
    entity_id: int
    student_id: Optional[int]
    class_id: Optional[int]
    enrollment_id: Optional[int]
    observed_amount: Decimal
    payment_date: date
    evidence: str
    review_guidance: str
    false_positive_note: str
    candidate_count: Optional[int] = None
    canonical_enrollment_id: Optional[int] = None
    linked_student_id: Optional[int] = None
    linked_class_id: Optional[int] = None


@dataclass(frozen=True)
class FinanceFindingsPage:
    state: str  # OK or ERROR; zero findings is OK with total_count == 0.
    as_of_date: date
    detected_at: datetime
    source_version: str
    page: int
    per_page: int
    total_count: Optional[int]
    counts_by_rule: dict[str, int]
    findings: tuple[FinanceFinding, ...]
    error_code: Optional[str] = None
