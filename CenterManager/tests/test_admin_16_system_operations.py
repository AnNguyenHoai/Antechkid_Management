from pathlib import Path
SRC=Path("src/centermanager")
def read(p): return (SRC/p).read_text(encoding="utf-8")
def test_system_operations_service_contract():
    s=read("services/system_operations_service.py")
    for token in ("class SystemOperationsService","Database","Runtime","Collaboration","Git Sync","Storage"):
        assert token in s
def test_system_operations_permission_and_navigation():
    p=read("models/permission.py")
    shell=read("ui/admin_workspace/admin_workspace_shell.py")
    assert 'SYSTEM_DIAGNOSTICS_VIEW = "system.diagnostics.view"' in p
    assert '"operations": PermissionDefinitions.SYSTEM_DIAGNOSTICS_VIEW' in shell
    assert '"label": "System Operations"' in shell
