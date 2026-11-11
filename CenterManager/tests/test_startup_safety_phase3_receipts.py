"""Recovery receipts are diagnostic: neither login nor WRITE authority.

The previous Phase-3 policy blocked editing on a lost Recovery receipt. The
business-approved policy now derives editing solely from Git MAIN, SQLCipher,
domain permission, remote lease and CAS.
"""
from pathlib import Path
from types import SimpleNamespace

from centermanager.platform.sync.offline_read_state import (
    offline_read_active, set_offline_read,
)


ROOT = Path(__file__).resolve().parents[1] / "src/centermanager"


def test_recovery_receipt_failure_does_not_activate_offline_write_fence():
    try:
        set_offline_read(False)
        assert not offline_read_active()
        app = (ROOT / "app.py").read_text(encoding="utf-8")
        assert "_degrade_startup_to_verified_read" not in app
        assert "Recovery receipt unavailable; accepted Git MAIN remains usable" in app
        assert not offline_read_active()
    finally:
        set_offline_read(False)


def test_recovery_receipt_does_not_gate_start_editing_or_mutation():
    tx = (ROOT / "services/write_transaction.py").read_text(encoding="utf-8")
    start = tx.split("def start_editing(", 1)[1].split("def finish_editing(", 1)[0]
    assert "require_replaceable()" not in start
    assert "self._verify_first_writer_consistency" in start
    assert "self._verify_grant_before_editing()" in start
    mutation = (ROOT / "database/mutation_authority.py").read_text(encoding="utf-8")
    assert "Recovery journal or repository identity changed" not in mutation
    assert "provider.observe_remote_main_commit() != pinned" in mutation
    assert "cm.is_writing()" in mutation


def test_no_recovery_latch_in_network_reconnect():
    sync = (ROOT / "platform/sync/runtime_sync_service.py").read_text(encoding="utf-8")
    authoritative = (
        ROOT / "platform/sync/authoritative_runtime_sync_service.py"
    ).read_text(encoding="utf-8")
    offline = (ROOT / "platform/sync/offline_read_state.py").read_text(encoding="utf-8")
    assert "receipt_read_only_active" not in sync
    assert "receipt_read_only_active" not in authoritative
    assert "protect_read_only_for_process" not in offline
    assert "WriteRecoveryJournal().assert_replaceable()" not in authoritative


def test_sqlcipher_schema_and_git_identity_are_still_mandatory():
    app = (ROOT / "app.py").read_text(encoding="utf-8")
    migration = (ROOT / "database/migration.py").read_text(encoding="utf-8")
    assert "verify_runtime_schema_readonly()" in app
    assert "ensure_schema()" in app
    assert "_validate_post_upgrade_schema(" in migration
    sync = (ROOT / "platform/sync/startup_sync.py").read_text(encoding="utf-8")
    assert "inspect_authoritative_database_for_startup(repo_db)" in sync
    assert "get_fetched_remote_main_commit() != accepted" in sync


def test_recovery_notice_does_not_rewrite_finance_or_grant_write():
    ui = (ROOT / "ui/main_window.py").read_text(encoding="utf-8")
    reminder = ui.split("def _show_pending_review_notices(", 1)[1].split(
        "def _show_pending_recovery_cases(", 1
    )[0]
    assert "queue.acknowledge(item" in reminder
    assert "publish_only(" not in reminder
    assert "Đã kiểm tra" in reminder and "Để lần sau" in reminder
