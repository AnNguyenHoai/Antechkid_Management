from pathlib import Path

from centermanager.core.capabilities import Capability
from centermanager.core.current_user import get_current_user
from centermanager.platform.backup.backup_service import BackupResult, BackupService
from centermanager.platform.backup.recovery_authority import (
    RecoveryAuthority,
    RecoveryAuthorityError,
)
from centermanager.platform.backup.recovery_publisher import (
    AuthoritativeRecoveryPublisher,
    RecoveryPublishError,
)
from centermanager.platform.backup.restore_authorization import issue_restore_authorization
from centermanager.services.audit_service import AuditService
from centermanager.services.authorization_service import AuthorizationService


class BackupRestoreError(RuntimeError):
    pass


class BackupRestoreAuthorizationError(BackupRestoreError):
    pass


class BackupRestoreValidationError(BackupRestoreError):
    pass


class BackupRestoreResult(BackupResult):
    """Restore outcome carrying the process-lifecycle safety boundary."""

    def __init__(self, success: bool, backup_path=None, error=None, *, requires_restart: bool = False):
        super().__init__(success=success, backup_path=backup_path, error=error)
        self.requires_restart = bool(requires_restart)


class BackupOperationsService:
    """Admin-facing backup/recovery orchestration with audit hooks."""

    def __init__(self, session_factory=None, backup_service=None, audit_service=None,
                 collaboration_manager=None, recovery_publisher=None):
        self._backup = backup_service or BackupService()
        self._audit = audit_service or (
            AuditService(session_factory) if session_factory is not None else None
        )
        self._collaboration_manager = collaboration_manager
        self._recovery_publisher = recovery_publisher

    def list_backups(self):
        return self._backup.list_backups()

    def create_backup(self, label="manual"):
        result = self._backup.create_backup(label=label)
        if result.success and self._audit:
            actor = get_current_user()
            self._audit.record(
                "BACKUP_CREATED", "admin", target_type="backup",
                target_id=str(result.backup_path), target_name=label, actor=actor,
                details={"path": str(result.backup_path)},
            )
        return result

    @staticmethod
    def confirmation_phrase(backup_path) -> str:
        name = Path(backup_path).name.strip()
        return f"RESTORE {name}"

    @staticmethod
    def confirmation_mismatch_detail(expected: str, actual: str) -> str:
        """Describe an exact-match failure without relaxing the security guard.

        The phrase contains only the non-secret backup identifier. Code points are
        included so packaged Windows UAT can distinguish invisible whitespace and
        look-alike Unicode characters that are indistinguishable in a Qt dialog.
        """
        expected = str(expected)
        actual = str(actual)
        limit = min(len(expected), len(actual))
        mismatch = next((i for i in range(limit) if expected[i] != actual[i]), None)
        if mismatch is None:
            mismatch = limit
        expected_cp = f"U+{ord(expected[mismatch]):04X}" if mismatch < len(expected) else "<end>"
        actual_cp = f"U+{ord(actual[mismatch]):04X}" if mismatch < len(actual) else "<end>"
        return (
            f"expected length={len(expected)}, actual length={len(actual)}, "
            f"first difference at position {mismatch + 1}: "
            f"expected {expected_cp}, actual {actual_cp}"
        )

    @staticmethod
    def _require_admin_and_capability():
        actor = get_current_user()
        if actor is None or not bool(getattr(actor, "is_admin", False)):
            raise BackupRestoreAuthorizationError("Administrator access is required.")
        try:
            AuthorizationService.require(actor, Capability.BACKUP_RESTORE)
        except Exception as exc:
            raise BackupRestoreAuthorizationError("Backup restore capability is required.") from exc
        return actor

    def _recovery_authority(self) -> RecoveryAuthority:
        manager = self._collaboration_manager
        try:
            initialized = bool(manager is not None and manager.is_initialized())
            writing = bool(initialized and manager.is_writing())
        except Exception as exc:
            raise BackupRestoreAuthorizationError("Unable to verify recovery entry state.") from exc
        if not initialized:
            raise BackupRestoreAuthorizationError("Recovery requires an initialized collaboration session.")
        if writing:
            raise BackupRestoreAuthorizationError(
                "Finish or cancel the current editing session before starting recovery."
            )
        return RecoveryAuthority(manager)

    def restore_backup(self, backup_path, *, reason: str, confirmation: str):
        backup_path = Path(backup_path)
        actor = self._require_admin_and_capability()
        clean_reason = str(reason or "").strip()
        if not clean_reason:
            raise BackupRestoreValidationError("A restore reason is required.")

        expected = self.confirmation_phrase(backup_path)
        actual = str(confirmation or "").strip()
        if actual != expected:
            detail = self.confirmation_mismatch_detail(expected, actual)
            raise BackupRestoreValidationError(
                f'Type "{expected}" to confirm this destructive operation. ({detail})'
            )

        authority = self._recovery_authority()
        try:
            authority.acquire()
        except RecoveryAuthorityError as exc:
            raise BackupRestoreAuthorizationError(str(exc)) from exc

        try:
            if not authority.validate():
                raise BackupRestoreAuthorizationError(
                    "Exclusive recovery authority was lost before safety backup."
                )

            safety = self._backup.create_backup(label="pre_restore")
            if not safety.success or safety.backup_path is None:
                return BackupRestoreResult(
                    success=False,
                    error=f"Pre-restore backup failed: {safety.error or 'unknown error'}",
                    requires_restart=False,
                )

            if not authority.renew():
                raise BackupRestoreAuthorizationError(
                    "Exclusive recovery authority was lost before restore."
                )

            authorization = issue_restore_authorization(
                actor=actor, reason=clean_reason, confirmation=expected,
            )
            result = self._backup.restore_backup(backup_path, authorization=authorization)
            if not result.success:
                return BackupRestoreResult(
                    success=False, backup_path=result.backup_path,
                    error=result.error, requires_restart=False,
                )

            publisher = self._recovery_publisher
            if publisher is None:
                return BackupRestoreResult(
                    success=False,
                    error=("Restore completed locally but authoritative recovery publish "
                           "is unavailable; recovery remains incomplete."),
                    requires_restart=True,
                )
            try:
                publisher.publish(
                    authority=authority,
                    actor_name=str(getattr(actor, "username", "") or "system"),
                    backup_name=backup_path.name,
                )
            except RecoveryPublishError as exc:
                return BackupRestoreResult(
                    success=False,
                    error=("Restore completed locally but authoritative recovery publish "
                           f"failed: {exc}"),
                    requires_restart=True,
                )

            if self._audit:
                self._audit.record(
                    "BACKUP_RESTORED", "admin", target_type="backup",
                    target_id=str(backup_path), target_name=backup_path.name, actor=actor,
                    details={
                        "reason": clean_reason,
                        "pre_restore_backup": str(safety.backup_path),
                        "restored_backup": str(backup_path),
                        "authority": "RECOVERY",
                        "authoritative_publish": True,
                        "restart_required": True,
                    },
                    summary=f"Admin restored backup {backup_path.name}",
                )
            return BackupRestoreResult(
                success=True, backup_path=result.backup_path,
                error=result.error, requires_restart=True,
            )
        finally:
            authority.release()
