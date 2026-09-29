from pathlib import Path

from centermanager.core.capabilities import Capability
from centermanager.core.current_user import get_current_user
from centermanager.platform.backup.backup_service import BackupResult, BackupService
from centermanager.platform.backup.restore_authorization import issue_restore_authorization
from centermanager.services.audit_service import AuditService
from centermanager.services.authorization_service import AuthorizationService


class BackupRestoreError(RuntimeError):
    pass


class BackupRestoreAuthorizationError(BackupRestoreError):
    pass


class BackupRestoreValidationError(BackupRestoreError):
    pass


class BackupOperationsService:
    """Admin-facing backup/recovery orchestration with audit hooks.

    Restore is intentionally treated as a destructive security boundary. UI
    checks are convenience only; this service validates the real principal,
    capability, recovery entry state, reason and typed confirmation before
    creating even the pre-restore safety snapshot.
    """

    def __init__(
        self,
        session_factory=None,
        backup_service=None,
        audit_service=None,
        collaboration_manager=None,
    ):
        self._backup = backup_service or BackupService()
        self._audit = audit_service or (
            AuditService(session_factory) if session_factory is not None else None
        )
        self._collaboration_manager = collaboration_manager

    def list_backups(self):
        return self._backup.list_backups()

    def create_backup(self, label="manual"):
        result = self._backup.create_backup(label=label)
        if result.success and self._audit:
            actor = get_current_user()
            self._audit.record(
                "BACKUP_CREATED",
                "admin",
                target_type="backup",
                target_id=str(result.backup_path),
                target_name=label,
                actor=actor,
                details={"path": str(result.backup_path)},
            )
        return result

    @staticmethod
    def confirmation_phrase(backup_path) -> str:
        name = Path(backup_path).name.strip()
        return f"RESTORE {name}"

    @staticmethod
    def _require_admin_and_capability():
        actor = get_current_user()
        if actor is None or not bool(getattr(actor, "is_admin", False)):
            raise BackupRestoreAuthorizationError("Administrator access is required.")
        try:
            AuthorizationService.require(actor, Capability.BACKUP_RESTORE)
        except Exception as exc:
            raise BackupRestoreAuthorizationError(
                "Backup restore capability is required."
            ) from exc
        return actor

    def _require_recovery_entry_state(self) -> None:
        """Fail closed until dedicated recovery authority exists.

        SEC06-13R separates Restore from the normal Start Editing -> Finish
        Editing transaction. Phase A blocks the legacy behavior where Restore
        ran while the current client owned normal WRITE. Phase B will add a
        dedicated recovery-authority path for READ state.
        """
        manager = self._collaboration_manager
        try:
            initialized = bool(manager is not None and manager.is_initialized())
            writing = bool(initialized and manager.is_writing())
        except Exception as exc:
            raise BackupRestoreAuthorizationError(
                "Unable to verify recovery entry state."
            ) from exc

        if writing:
            raise BackupRestoreAuthorizationError(
                "Finish or cancel the current editing session before starting recovery."
            )

        # Phase A intentionally leaves Restore unavailable from READ as well.
        # Dedicated exclusive recovery authority is introduced in SEC06-13R-B.
        raise BackupRestoreAuthorizationError(
            "Recovery authority is not available yet; Restore is temporarily disabled."
        )

    def restore_backup(self, backup_path, *, reason: str, confirmation: str):
        backup_path = Path(backup_path)

        # All destructive-operation intent checks happen before any mutation,
        # including the safety backup creation.
        actor = self._require_admin_and_capability()
        self._require_recovery_entry_state()

        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise BackupRestoreValidationError("A restore reason is required.")

        expected = self.confirmation_phrase(backup_path)
        if str(confirmation or "").strip() != expected:
            raise BackupRestoreValidationError(
                f'Type "{expected}" to confirm this destructive operation.'
            )

        safety = self._backup.create_backup(label="pre_restore")
        if not safety.success or safety.backup_path is None:
            return BackupResult(
                success=False,
                error=f"Pre-restore backup failed: {safety.error or 'unknown error'}",
            )

        # SEC06-13R-B will revalidate dedicated recovery authority here before
        # issuing raw platform authorization. The Phase-A entry gate above is
        # intentionally fail-closed, so this code cannot currently be reached.
        self._require_recovery_entry_state()
        authorization = issue_restore_authorization(
            actor=actor,
            reason=clean_reason,
            confirmation=expected,
        )
        result = self._backup.restore_backup(
            backup_path,
            authorization=authorization,
        )
        if result.success and self._audit:
            self._audit.record(
                "BACKUP_RESTORED",
                "admin",
                target_type="backup",
                target_id=str(backup_path),
                target_name=backup_path.name,
                actor=actor,
                details={
                    "reason": clean_reason,
                    "pre_restore_backup": str(safety.backup_path),
                    "restored_backup": str(backup_path),
                },
                summary=f"Admin restored backup {backup_path.name}",
            )
        return result
