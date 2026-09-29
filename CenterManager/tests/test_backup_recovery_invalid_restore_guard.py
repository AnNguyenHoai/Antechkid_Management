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


def test_restore_button_requires_integrity_valid_backup_and_stays_disabled_in_phase_a():
    source = _source()

    assert "restore_eligible = bool(backup and self._is_restore_eligible(backup))" in source
    assert "self.restore_btn.setEnabled(False)" in source
    assert "self.restore_btn.setEnabled(write and admin and restore_eligible)" not in source


def test_restore_handler_rechecks_integrity_before_phase_a_recovery_guards():
    source = _source()

    integrity_guard = "if not self._is_restore_eligible(backup):"
    write_guard = "if can_write(self._cm):"
    disabled_message = (
        "Restore is temporarily disabled until dedicated recovery authority is available."
    )

    assert integrity_guard in source
    assert write_guard in source
    assert source.index(integrity_guard) < source.index(write_guard)
    assert "Restore rejected: selected backup did not pass integrity validation." in source
    assert disabled_message in source


def test_phase_a_ui_contains_no_destructive_restore_service_call():
    source = _source()

    assert "result = self._service.restore_backup(" not in source
    assert "expected = self._service.confirmation_phrase(backup_path)" not in source
