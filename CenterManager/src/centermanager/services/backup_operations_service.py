from pathlib import Path

from centermanager.core.capabilities import Capability
from centermanager.core.current_user import get_current_user
from centermanager.platform.backup.backup_service import (
    BackupResult,
    BackupService,
    _issue_restore_authorization,
)
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
    capability, WRITE ownership, reason and typed confirmation before creating
    even the pre-restore safety snapshot.
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

    def _require_write(self) -> None:
        manager = self._collaboration_manager
        try:
            writable = bool(
                manager is not None
                and manager.is_initialized()
                and manager.is_writing()
            )
        except Exception:
            writable = False
        if not writable:
            raise BackupRestoreAuthorizationError(
                "WRITE mode is required before restoring a backup."
            )

    def restore_backup(self, backup_path, *, reason: str, confirmation: str):
        backup_path = Path(backup_path)

        # All destructive-operation intent checks happen before any mutation,
        # including the safety backup creation.
        actor = self._require_admin_and_capability()
        self._require_write()

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

        # Safety backup may take long enough for collaboration ownership to
        # change. Revalidate WRITE immediately before issuing raw authorization.
        self._require_write()
        authorization = _issue_restore_authorization(
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
