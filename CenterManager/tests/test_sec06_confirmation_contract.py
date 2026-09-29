from pathlib import Path

from centermanager.services.backup_operations_service import BackupOperationsService


def test_sec06_confirmation_phrase_matches_real_publish_backup_shape(tmp_path):
    backup = tmp_path / "runtime" / "Backup" / "publish" / "manual_20260929_223705_d61bd79a"
    backup.mkdir(parents=True)

    phrase = BackupOperationsService.confirmation_phrase(backup)

    assert phrase == "RESTORE manual_20260929_223705_d61bd79a"


def test_sec06_confirmation_diagnostic_identifies_invisible_character():
    expected = "RESTORE manual_20260929_223705_d61bd79a"
    actual = "RESTORE\u00a0manual_20260929_223705_d61bd79a"

    detail = BackupOperationsService.confirmation_mismatch_detail(expected, actual)

    assert "expected length=40" in detail
    assert "actual length=40" in detail
    assert "position 8" in detail
    assert "expected U+0020" in detail
    assert "actual U+00A0" in detail


def test_sec06_confirmation_diagnostic_identifies_extra_character():
    expected = "RESTORE manual_20260929_223705_d61bd79a"
    actual = "RESTORE  manual_20260929_223705_d61bd79a"

    detail = BackupOperationsService.confirmation_mismatch_detail(expected, actual)

    assert "expected length=40" in detail
    assert "actual length=41" in detail
    assert "position 9" in detail
