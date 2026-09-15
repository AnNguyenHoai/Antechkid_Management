from pathlib import Path
SRC=Path('src/centermanager')
def read(p): return (SRC/p).read_text(encoding='utf-8')
def test_audit_model_and_service_exist():
    assert 'class AuditLog' in read('models/audit_log.py')
    assert 'class AuditService' in read('services/audit_service.py')
def test_audit_permission_and_navigation_exist():
    assert 'AUDIT_VIEW = "audit.view"' in read('models/permission.py')
    s=read('ui/admin_workspace/admin_workspace_shell.py')
    assert '"audit": PermissionDefinitions.AUDIT_VIEW' in s
    assert '"label": "Audit Log"' in s
def test_permission_service_emits_audit_events():
    s=read('services/permission_service.py')
    assert 'ROLE_CREATED' in s and 'USER_PASSWORD_RESET' in s and 'USER_ACTIVATED' in s
