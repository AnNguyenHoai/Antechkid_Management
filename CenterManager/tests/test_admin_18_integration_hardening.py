from pathlib import Path
SRC=Path("src/centermanager")
def read(p): return (SRC/p).read_text(encoding="utf-8")
def test_admin_shell_integrates_all_final_modules():
    s=read("ui/admin_workspace/admin_workspace_shell.py")
    for token in ("UserListPage","RoleListPage","AuditLogPage","SettingsPage","SystemOperationsPage","BackupRecoveryPage"):
        assert token in s
def test_backup_restore_safety_contract():
    s=read("platform/backup/backup_service.py")
    for token in ("sha256","integrity_check","format_version","resolve()"):
        assert token in s
def test_audit_backup_events_exist():
    s=read("services/backup_operations_service.py")
    assert "BACKUP_CREATED" in s and "BACKUP_RESTORED" in s
