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


def test_restore_eligibility_is_fail_closed():
    source = _source()

    assert '== "valid"' in source
    assert 'backup.get("status") or ""' in source


def test_restore_button_requires_integrity_valid_backup():
    source = _source()

    assert "restore_eligible = bool(backup and self._is_restore_eligible(backup))" in source
    assert "self.restore_btn.setEnabled(write and admin and restore_eligible)" in source


def test_restore_handler_rechecks_integrity_before_destructive_flow():
    source = _source()

    guard = "if not self._is_restore_eligible(backup):"
    restore_call = "result = self._service.restore_backup("
    confirmation = "expected = self._service.confirmation_phrase(backup_path)"

    assert guard in source
    assert source.index(guard) < source.index(confirmation)
    assert source.index(guard) < source.index(restore_call)
    assert "Restore rejected: selected backup did not pass integrity validation." in source
