"""Evidence collector for a safe future-only monthly Enrollment opt-in.

Production orchestration must supply an encrypted backup under the managed
backup root and a reconciliation verifier. Calling the activation command
without this collector fails closed.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path

from centermanager.core.clock import get_clock
from centermanager.database.encryption import database_encryption_required
from centermanager.database.mutation_authority import gate_for
from centermanager.platform.backup.backup_service import BackupService
from centermanager.services.monthly_tuition_migration_gate import EnrollmentMigrationEvidence


class VerifiedMonthlyTuitionPreflight:
    """Recheck existing backup integrity, reconciliation and active WRITE.

    The backup is never created implicitly during a DB transaction. An
    operator must create/verify an encrypted copy BEFORE starting opt-in.
    """

    def __init__(self, backup_path, *, reconciliation_verifier,
                 backup_service=None, write_verifier=None):
        self._backup_path = Path(backup_path).resolve()
        if not callable(reconciliation_verifier):
            raise ValueError("A live reconciliation verifier is mandatory")
        self._reconciliation_verifier = reconciliation_verifier
        self._backup_service = backup_service or BackupService()
        self._write_verifier = write_verifier or self._check_write

    @staticmethod
    def _check_write() -> bool:
        try:
            gate_for().require("business", permissions=("tuition.enrollment.override",))
        except Exception:
            return False
        return True

    def _backup_verified(self) -> bool:
        try:
            if not database_encryption_required():
                return False
            valid, _detail = self._backup_service._validate_backup(self._backup_path)
            if not valid:
                return False
            manifest = json.loads(
                (self._backup_path / "manifest.json").read_text(encoding="utf-8")
            )
            if manifest.get("database_encrypted") is not True:
                return False
            created = datetime.fromisoformat(manifest["created_at"])
            # Avoid approving a stale historic backup as the opt-in snapshot.
            age = datetime.now() - created
            return timedelta(seconds=0) <= age <= timedelta(hours=1)
        except Exception:
            return False

    def __call__(self, db, enrollment, effective_from):
        repo = db
        del repo
        # Lack of an explicit reconciliation result is conservatively blocked.
        try:
            unresolved = self._reconciliation_verifier(db, enrollment)
            if type(unresolved) is not bool:
                unresolved = True
        except Exception:
            unresolved = True
        try:
            write_valid = self._write_verifier() is True
        except Exception:
            write_valid = False
        return EnrollmentMigrationEvidence(
            enrollment_id=int(enrollment.id),
            requested_effective_date=effective_from,
            review_date=get_clock().today(),
            first_enrollment_date=enrollment.start_date or get_clock().today(),
            legacy_tuition_resolved=bool(enrollment.has_tuition_contract),
            has_unattributed_payment=bool(self._unattributed(db, enrollment)),
            already_monthly=bool(self._already_monthly(db, enrollment)),
            has_unresolved_reconciliation=unresolved,
            encrypted_backup_verified=self._backup_verified(),
            write_authority_verified=write_valid,
        )

    @staticmethod
    def _unattributed(db, enrollment):
        from centermanager.repositories.monthly_tuition_repository import MonthlyTuitionRepository
        return MonthlyTuitionRepository(db).unattributed_tuition_receipt(
            enrollment.student_id, enrollment.class_id,
        )

    @staticmethod
    def _already_monthly(db, enrollment):
        from centermanager.repositories.monthly_tuition_repository import MonthlyTuitionRepository
        return MonthlyTuitionRepository(db).term(enrollment.id) is not None
