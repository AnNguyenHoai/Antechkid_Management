from pathlib import Path


SOURCE = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "centermanager"
    / "ui"
    / "admin_workspace"
    / "backup_recovery_page.py"
)


def _source():
    return SOURCE.read_text(encoding="utf-8")


def _restore_handler_source(source: str) -> str:
    """Limit ordering assertions to restore_selected, not other page handlers."""
    start = source.index("    def restore_selected(self):")
    return source[start:]


def test_restore_eligibility_is_fail_closed():
    source = _source()

    assert '== "valid"' in source
    assert 'backup.get("status") or ""' in source


def test_restore_button_requires_integrity_valid_backup_and_dedicated_recovery_entry():
    """SEC06-13R-C2 supersedes the Phase-A always-disabled restore contract."""
    source = _source()

    assert "restore_eligible = bool(backup and self._is_restore_eligible(backup))" in source
    assert 'permitted = self._ps.has_permission("backup.restore")' in source
    assert "bool(not write and restore_eligible and permitted)" in source
    assert "self.restore_btn.setEnabled(write and admin and restore_eligible)" not in source


def test_restore_handler_rechecks_integrity_before_recovery_guards():
    source = _restore_handler_source(_source())

    integrity_guard = "if not self._is_restore_eligible(backup):"
    write_guard = "if can_write(self._cm):"
    capability_guard = 'if not self._ps.has_permission("backup.restore"):'

    assert integrity_guard in source
    assert write_guard in source
    assert capability_guard in source
    assert source.index(integrity_guard) < source.index(write_guard)
    assert source.index(write_guard) < source.index(capability_guard)
    assert "Restore rejected: selected backup did not pass integrity validation." in source
    assert "Finish or cancel the current editing session before starting recovery." in source


def test_c2_ui_routes_destructive_restore_through_guarded_service_boundary():
    """C2 activates GUI restore only through the hardened orchestration service."""
    source = _source()

    assert "expected = self._service.confirmation_phrase(backup_path)" in source
    assert "result = self._service.restore_backup(" in source
    assert "reason=reason" in source
    assert "confirmation=confirmation" in source
    assert "authoritative recovery publish completed" in source
    assert "Recovery incomplete:" in source
