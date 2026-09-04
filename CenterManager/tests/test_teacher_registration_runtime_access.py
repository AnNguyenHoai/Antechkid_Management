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
    assert '"admin": None' in source
    assert 'if not user or not user.is_admin:' in source
    assert 'Permission denied for admin workspace' in source


def test_admin_workspace_pages_have_admin_role_boundary():
    source = (
        ROOT / "src" / "centermanager" / "ui" / "admin_workspace"
        / "admin_workspace_shell.py"
    ).read_text(encoding="utf-8")
    assert "user = get_current_user()" in source
    assert "if user is None or not user.is_admin:" in source
