from pathlib import Path

ROOT = Path("src/centermanager")

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_admin_pages_do_not_call_ensure_write_directly():
    for rel in [
        "ui/admin_workspace/user_list_page.py",
        "ui/admin_workspace/settings_page.py",
        "ui/admin_workspace/git_settings_page.py",
    ]:
        assert ".ensure_write()" not in read(rel)

def test_admin_access_helper_handles_uninitialized_collaboration():
    source = read("ui/admin_workspace/access.py")
    assert "if not collaboration_manager.is_initialized()" in source
    assert "except Exception:" in source
    assert "return False" in source

def test_admin_shell_uses_one_notification_service():
    source = read("ui/admin_workspace/admin_workspace_shell.py")
    assert "notification_service or NotificationService()" in source
    assert source.count("self._notification_service") >= 4

def test_admin_shell_has_page_permission_boundaries():
    source = read("ui/admin_workspace/admin_workspace_shell.py")
    assert '"users": PermissionDefinitions.USER_VIEW' in source
    assert '"settings": PermissionDefinitions.SETTING_UPDATE' in source
    assert '"git": PermissionDefinitions.SETTING_UPDATE' in source
    assert "def _has_page_permission" in source

def test_admin_write_actions_are_gated():
    user = read("ui/admin_workspace/user_list_page.py")
    settings = read("ui/admin_workspace/settings_page.py")
    git = read("ui/admin_workspace/git_settings_page.py")
    assert "self._write_enabled = bool(enabled)" in user
    assert "self.save_btn.setEnabled(enabled)" in settings
    assert "self._bundle_valid" in git
    assert "self.save_btn.setEnabled(" in git

def test_git_save_requires_validated_bundle_and_write_mode():
    source = read("ui/admin_workspace/git_settings_page.py")
    assert "self._bundle_valid" in source
    assert "self._write_enabled and editable and has_text and self._bundle_valid" in source
    assert "if not can_write(self._collaboration_manager):" in source
