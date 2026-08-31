from pathlib import Path
SRC=Path("src/centermanager")
def read(p): return (SRC/p).read_text(encoding="utf-8")
def test_backup_permissions_exist():
    s=read("models/permission.py")
    for token in ('backup.view','backup.create','backup.restore'):
        assert token in s
def test_backup_operations_service_has_audit_and_safety_snapshot():
    s=read("services/backup_operations_service.py")
    assert "BACKUP_CREATED" in s and "BACKUP_RESTORED" in s and "pre_restore" in s
def test_backup_page_is_integrated():
    s=read("ui/admin_workspace/admin_workspace_shell.py")
    assert "BackupRecoveryPage" in s and '"backup"' in s
