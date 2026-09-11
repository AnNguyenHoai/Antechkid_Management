from pathlib import Path
SRC = Path("src/centermanager")
def read(rel): return (SRC / rel).read_text(encoding="utf-8")

def test_lifecycle_error_exists():
    assert "class UserLifecycleError" in read("services/permission_service.py")

def test_management_lists_inactive_accounts():
    assert "return session.query(User).all()" in read("services/permission_service.py")

def test_both_create_paths_check_duplicate_username():
    source = read("services/permission_service.py")
    assert source.count("get_by_username(username)") >= 2

def test_self_deactivation_and_last_admin_are_blocked():
    source = read("services/permission_service.py")
    assert 'self._ensure_not_current_user(user_id, "deactivate")' in source
    assert 'self._ensure_not_last_admin(session, user, "deactivate")' in source

def test_admin_demotion_is_protected():
    source = read("services/permission_service.py")
    assert 'self._ensure_not_current_user(user_id, "remove administrator access from")' in source
    assert 'self._ensure_not_last_admin(session, user, "remove administrator access from")' in source

def test_delete_is_protected():
    source = read("services/permission_service.py")
    assert 'self._ensure_not_current_user(user_id, "delete")' in source
    assert 'self._ensure_not_last_admin(session, user, "delete")' in source

def test_password_reset_forces_change_and_clears_lock():
    source = read("services/permission_service.py")
    assert "def reset_user_password" in source
    assert "user.force_password_change = True" in source
    assert "user.login_attempts = 0" in source
    assert "user.locked_until = None" in source

def test_ui_double_click_respects_read_only_mode():
    assert "if not self._write_enabled:" in read("ui/admin_workspace/user_list_page.py")
