from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def test_runtime_teacher_registration_repair_is_latest_single_step():
    migration = ROOT / "migrations" / "versions" / "1e10a017_repair_teacher_registration_self_access.py"
    source = migration.read_text(encoding="utf-8")
    assert 'revision = "1e10a017"' in source
    assert 'down_revision = "1e10a016"' in source
    assert 'SELF_PERMISSION = "work_registration.self"' in source
    assert 'TEACHER_ROLE = "teacher"' in source
    assert "INSERT OR IGNORE INTO role_permissions" in source


def test_admin_workspace_is_reserved_for_admin_accounts():
    source = (ROOT / "src" / "centermanager" / "ui" / "main_window.py").read_text(encoding="utf-8")

    # Admin Workspace requires user.manage at the top-level workspace router,
    # while the Admin shell enforces the concrete admin-role boundary.
    assert '"admin": "user.manage"' in source
    assert '"admin": None' not in source
    assert 'if required_perm:' in source
    assert 'if not self._permission_helper.has_permission(required_perm):' in source
    assert 'if workspace_id == "admin":' in source


def test_admin_workspace_has_admin_role_boundary_without_employee_work_page():
    source = (
        ROOT / "src" / "centermanager" / "ui" / "admin_workspace"
        / "admin_workspace_shell.py"
    ).read_text(encoding="utf-8")
    assert "user = get_current_user()" in source
    assert "user.is_admin" in source
    assert "Permission denied for" in source
    assert "AdminEmployeeWorkDataPage" not in source
    assert '"employee_work_data"' not in source
