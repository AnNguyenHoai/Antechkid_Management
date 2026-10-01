import inspect

from centermanager.ui.admin_workspace.backup_recovery_page import BackupRecoveryPage


def test_post_restore_restart_fences_window_before_qt_exit():
    source = inspect.getsource(BackupRecoveryPage._terminate_for_recovery_restart)

    fence_at = source.index("root.setEnabled(False)")
    exit_at = source.index("app.exit(RECOVERY_RESTART_EXIT_CODE)")

    assert fence_at < exit_at


def test_restore_success_routes_restart_required_result_to_process_fence():
    source = inspect.getsource(BackupRecoveryPage.restore_selected)

    restart_flag_at = source.index('getattr(result, "requires_restart", False)')
    terminate_at = source.index("_terminate_for_recovery_restart(success=True)")

    assert restart_flag_at < terminate_at
