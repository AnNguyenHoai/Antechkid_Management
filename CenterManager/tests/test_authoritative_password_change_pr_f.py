from pathlib import Path

SRC = Path("src/centermanager")


def read(rel):
    return (SRC / rel).read_text(encoding="utf-8")


def test_production_login_defers_forced_password_mutation_until_write_is_ready():
    app = read("app.py")
    login = read("ui/login_dialog.py")

    assert "defer_forced_password_change=True" in app
    assert "user.force_password_change and not self._defer_forced_password_change" in login


def test_authoritative_password_flow_uses_existing_write_transaction_boundary():
    source = read("ui/authoritative_password_change.py")

    assert "self._transaction.start_editing()" in source
    assert "fresh_user = self._permission_service.get_user(self._user_id)" in source
    assert "self._transaction.mark_dirty()" in source
    assert "self._transaction.finish_editing(" in source
    assert "on_publish_success=self._on_publish_success" in source


def test_password_flow_waits_for_authoritative_grant_and_fails_closed():
    source = read("ui/authoritative_password_change.py")

    assert "WriteTransactionState.WAITING" in source
    assert "WriteGranted" in source
    assert "self._transaction.on_write_granted()" in source
    assert "Workspace access is blocked" in source


def test_password_flow_does_not_implement_direct_git_publication():
    source = read("ui/authoritative_password_change.py").lower()

    assert "git push" not in source
    assert "publish_only(" not in source
    assert "runtime_sync_service" not in source


def test_password_flow_rejects_stale_pre_handoff_credentials():
    source = read("ui/authoritative_password_change.py")

    assert "credentials changed on another computer" in source
    assert "sign in with the current password" in source


def test_workspace_unlock_waits_until_transaction_returns_to_idle():
    source = read("ui/authoritative_password_change.py")

    assert "QTimer.singleShot(0, self._verify_and_complete_after_publish)" in source
    assert "self._transaction.state != WriteTransactionState.IDLE" in source


def test_password_flow_rejects_authorization_changes_during_handoff():
    source = read("ui/authoritative_password_change.py")

    assert 'getattr(fresh_user, "is_active", False)' in source
    assert 'getattr(fresh_user, "role_id", None) != self._role_id' in source
    assert "permissions can be rebuilt safely" in source
