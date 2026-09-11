from pathlib import Path
SRC = Path('src/centermanager')
def read(rel): return (SRC / rel).read_text(encoding='utf-8')

def test_role_permissions_are_registered():
    source = read('models/permission.py')
    assert 'ROLE_VIEW = "role.view"' in source
    assert 'ROLE_MANAGE = "role.manage"' in source

def test_admin_shell_exposes_role_page():
    source = read('ui/admin_workspace/admin_workspace_shell.py')
    assert '"roles": PermissionDefinitions.ROLE_MANAGE' in source
    assert '"label": "Roles & Permissions"' in source

def test_role_service_has_lifecycle_guards():
    source = read('services/permission_service.py')
    assert 'class RoleLifecycleError' in source
    assert 'def create_role(' in source
    assert 'def update_role(' in source
    assert 'def delete_role(' in source
    assert 'Protected system roles cannot be deleted.' in source
    assert 'A role assigned to users cannot be deleted.' in source

def test_system_role_permissions_are_protected():
    source = read('services/permission_service.py')
    assert 'Permissions of protected system roles cannot be changed.' in source

def test_user_form_uses_database_roles():
    source = read('ui/admin_workspace/user_form_dialog.py')
    assert 'roles = self._service.get_all_roles()' in source
