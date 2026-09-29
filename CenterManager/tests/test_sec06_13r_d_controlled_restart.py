from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVICE = ROOT / "src" / "centermanager" / "services" / "backup_operations_service.py"
PAGE = ROOT / "src" / "centermanager" / "ui" / "admin_workspace" / "backup_recovery_page.py"
SHELL = ROOT / "src" / "centermanager" / "ui" / "admin_workspace" / "admin_workspace_shell.py"


def _text(path):
    return path.read_text(encoding="utf-8")


def test_destructive_restore_marks_every_post_mutation_return_restart_required():
    source = _text(SERVICE)
    mutation = "result = self._backup.restore_backup("
    post_mutation = source[source.index(mutation):]

    assert "class BackupRestoreResult(BackupResult):" in source
    assert post_mutation.count("requires_restart=True") >= 3
    assert "requires_restart=False" in source[: source.index(mutation)]
    assert "restart_required\": True" in post_mutation


def test_gui_terminates_stale_process_instead_of_hot_reloading_or_finishing_editing():
    source = _text(PAGE)

    assert "RECOVERY_RESTART_EXIT_CODE = 86" in source
    assert "app.exit(RECOVERY_RESTART_EXIT_CODE)" in source
    assert "if restart_required:" in source
    assert "_terminate_for_recovery_restart(success=True)" in source
    assert "_terminate_for_recovery_restart(success=False" in source
    assert "Finish Editing" in source  # explicitly documented as forbidden path
    assert "refresh_runtime_db" not in source


def test_gui_binds_existing_runtime_sync_service_for_authoritative_publish():
    page = _text(PAGE)
    shell = _text(SHELL)

    assert "AuthoritativeRecoveryPublisher(runtime_sync)" in page
    assert 'runtime_sync = getattr(root, "_sync_service", None)' in page
    assert "AuthoritativeRecoveryPublisher(self._runtime_sync_service)" in shell
    assert "recovery_publisher=recovery_publisher" in shell
