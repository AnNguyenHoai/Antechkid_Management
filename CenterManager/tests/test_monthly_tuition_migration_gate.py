from datetime import date
from dataclasses import replace

from centermanager.services.monthly_tuition_migration_gate import (
    EnrollmentMigrationEvidence, MigrationBlocker, assess_enrollment_migration,
)


def sample_evidence():
    return EnrollmentMigrationEvidence(
        enrollment_id=101,
        requested_effective_date=date(2026, 12, 1),
        review_date=date(2026, 11, 8),
        first_enrollment_date=date(2026, 9, 1),
        legacy_tuition_resolved=True,
        has_unattributed_payment=False,
        already_monthly=False,
        has_unresolved_reconciliation=False,
        encrypted_backup_verified=True,
        write_authority_verified=True,
    )


def test_future_opt_in_can_pass_when_evidence_complete():
    result = assess_enrollment_migration(sample_evidence())
    assert result.may_activate and not result.blockers


def test_retroactive_and_midmonth_switch_rejected():
    evidence = sample_evidence()
    assert MigrationBlocker.RETROACTIVE_START in assess_enrollment_migration(
        replace(evidence, requested_effective_date=date(2026, 10, 1))).blockers
    assert MigrationBlocker.RETROACTIVE_START in assess_enrollment_migration(
        replace(evidence, requested_effective_date=date(2026, 12, 10))).blockers


def test_unattributed_payment_and_missing_backup_fail_closed():
    evidence = replace(sample_evidence(), has_unattributed_payment=True,
        encrypted_backup_verified=False, write_authority_verified=False)
    result = assess_enrollment_migration(evidence)
    assert not result.may_activate
    assert MigrationBlocker.UNATTRIBUTED_TUITION_PAYMENT in result.blockers
    assert MigrationBlocker.NO_BACKUP in result.blockers
    assert MigrationBlocker.INACTIVE_WRITE in result.blockers


def test_legacy_unresolved_and_repeated_activation_fail_closed():
    evidence = replace(sample_evidence(), legacy_tuition_resolved=False,
        already_monthly=True, has_unresolved_reconciliation=True)
    result = assess_enrollment_migration(evidence)
    assert MigrationBlocker.HISTORICAL_TUITION_UNRESOLVED in result.blockers
    assert MigrationBlocker.ALREADY_MONTHLY in result.blockers
    assert MigrationBlocker.UNSETTLED_RECONCILIATION in result.blockers
