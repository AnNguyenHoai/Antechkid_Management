from pathlib import Path
from typing import Optional
from centermanager.platform.backup import BackupService
from centermanager.core.current_user import get_current_user
from centermanager.services.audit_service import AuditService

class BackupOperationsService:
    """Administrative facade around runtime backups with audit integration."""
    def __init__(self, backup_service: Optional[BackupService]=None, audit_service: Optional[AuditService]=None):
        self._backup=backup_service or BackupService()
        self._audit=audit_service
    def list_backups(self): return self._backup.list_backups()
    def create_backup(self, label="manual"):
        result=self._backup.create_backup(label)
        if self._audit: self._audit.record('BACKUP_CREATED','admin','backup',str(result.backup_path) if result.backup_path else None,label,result='success' if result.success else 'failed',details={'error':result.error},actor=get_current_user())
        return result
    def restore_backup(self, path):
        # Always capture current state before a destructive restore.
        safety=self._backup.create_backup('pre_restore')
        if not safety.success: return type(safety)(False,error=f'Pre-restore backup failed: {safety.error}')
        result=self._backup.restore_backup(Path(path))
        if self._audit: self._audit.record('BACKUP_RESTORED','admin','backup',str(path),Path(path).name,result='success' if result.success else 'failed',details={'safety_backup':str(safety.backup_path),'error':result.error},actor=get_current_user())
        return result
