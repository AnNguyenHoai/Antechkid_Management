"""Explicit, fail-closed assessment before switching an Enrollment to monthly fees.

Read-only policy. The caller supplies evidence from *authoritative* SQLCipher
queries; this module must not make assumptions about historical records.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import Enum


class MigrationBlocker(str, Enum):
    RETROACTIVE_START = "RETROACTIVE_START"
    HISTORICAL_TUITION_UNRESOLVED = "HISTORICAL_TUITION_UNRESOLVED"
    UNATTRIBUTED_TUITION_PAYMENT = "UNATTRIBUTED_TUITION_PAYMENT"
    ALREADY_MONTHLY = "ALREADY_MONTHLY"
    UNSETTLED_RECONCILIATION = "UNSETTLED_RECONCILIATION"
    NO_BACKUP = "NO_BACKUP"
    INACTIVE_WRITE = "INACTIVE_WRITE"


@dataclass(frozen=True)
class EnrollmentMigrationEvidence:
    enrollment_id: int
    requested_effective_date: date
    review_date: date
    first_enrollment_date: date
    legacy_tuition_resolved: bool
    has_unattributed_payment: bool
    already_monthly: bool
    has_unresolved_reconciliation: bool
    encrypted_backup_verified: bool
    write_authority_verified: bool


@dataclass(frozen=True)
class MigrationAssessment:
    enrollment_id: int
    blockers: tuple[MigrationBlocker, ...]

    @property
    def may_activate(self) -> bool:
        return not self.blockers


def assess_enrollment_migration(evidence: EnrollmentMigrationEvidence) -> MigrationAssessment:
    if type(evidence.enrollment_id) is not int or evidence.enrollment_id <= 0:
        raise ValueError("enrollment_id must be positive")
    if any(type(item) is not date for item in (
        evidence.requested_effective_date, evidence.review_date, evidence.first_enrollment_date
    )):
        raise ValueError("migration dates must be valid")
    blockers = []
    if (evidence.requested_effective_date < evidence.review_date.replace(day=1)
            or evidence.requested_effective_date.day != 1):
        blockers.append(MigrationBlocker.RETROACTIVE_START)
    if not evidence.legacy_tuition_resolved:
        blockers.append(MigrationBlocker.HISTORICAL_TUITION_UNRESOLVED)
    if evidence.has_unattributed_payment:
        blockers.append(MigrationBlocker.UNATTRIBUTED_TUITION_PAYMENT)
    if evidence.already_monthly:
        blockers.append(MigrationBlocker.ALREADY_MONTHLY)
    if evidence.has_unresolved_reconciliation:
        blockers.append(MigrationBlocker.UNSETTLED_RECONCILIATION)
    if not evidence.encrypted_backup_verified:
        blockers.append(MigrationBlocker.NO_BACKUP)
    if not evidence.write_authority_verified:
        blockers.append(MigrationBlocker.INACTIVE_WRITE)
    return MigrationAssessment(evidence.enrollment_id, tuple(blockers))
