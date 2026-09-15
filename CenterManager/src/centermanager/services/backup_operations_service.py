from pathlib import Path
from centermanager.platform.backup.backup_service import BackupService
from centermanager.services.audit_service import AuditService

class BackupOperationsService:
    """Admin-facing backup/recovery orchestration with audit hooks."""
    def __init__(self, session_factory=None, backup_service=None, audit_service=None):
        """Create the backup/recovery orchestration service.

        ``audit_service`` is accepted for dependency injection from the Admin
        workspace. ``session_factory`` remains supported for backwards
        compatibility and is used to construct an AuditService only when an
        explicit audit service was not supplied.
        """
        self._backup = backup_service or BackupService()
        self._audit = audit_service or (
            AuditService(session_factory) if session_factory is not None else None
        )

    def list_backups(self):
        return self._backup.list_backups()

    def create_backup(self, label='manual'):
        result = self._backup.create_backup(label=label)
        if result.success and self._audit:
            self._audit.record('BACKUP_CREATED', 'admin', 'backup', str(result.backup_path), label, details={'path': str(result.backup_path)})
        return result

    def restore_backup(self, backup_path):
        backup_path = Path(backup_path)
        # Safety snapshot must be taken before destructive restore.
        safety = self._backup.create_backup(label='pre_restore')
        if not safety.success:
            return type(safety)(success=False, error=f'Pre-restore backup failed: {safety.error}')
        result = self._backup.restore_backup(backup_path)
        if result.success and self._audit:
            self._audit.record('BACKUP_RESTORED', 'admin', 'backup', str(backup_path), backup_path.name, details={'pre_restore_backup': str(safety.backup_path)})
        return result
