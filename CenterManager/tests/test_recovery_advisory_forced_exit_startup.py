"""Forced-exit Recovery is an advisory workflow after a separately verified MAIN.

Regression for 2026-11-11 log: startup fetch and SQLCipher preflight succeeded,
then ensure_schema -> system_mutation_permit -> assert_replaceable() rejected the
old OPEN journal. That journal must not veto an otherwise current schema.
"""
from pathlib import Path
from types import SimpleNamespace

import pytest

from centermanager.app import _requires_readonly_schema_for_recovery
from centermanager.platform.recovery_review_notices import RecoveryReviewNotices
from centermanager.platform.sync import offline_read_state


def test_forced_finish_editing_old_open_journal_selects_readonly_schema():
    assert _requires_readonly_schema_for_recovery(
        offline_read=False,
        review_main="a" * 40,
        manual_main=None,
        unverified_receipt=False,
    )


def test_dirty_or_unreadable_old_receipt_cannot_invoke_migration():
    assert _requires_readonly_schema_for_recovery(
        offline_read=False,
        review_main=None,
        manual_main=None,
        unverified_receipt=True,
    )


@pytest.mark.parametrize("kwargs", [
    dict(offline_read=True, review_main=None, manual_main=None,
         unverified_receipt=False),
    dict(offline_read=False, review_main=None, manual_main="a" * 40,
         unverified_receipt=False),
])
def test_all_readonly_admissions_remain_readonly(kwargs):
    assert _requires_readonly_schema_for_recovery(**kwargs)


def test_clean_verified_current_main_can_use_existing_schema_path():
    assert not _requires_readonly_schema_for_recovery(
        offline_read=False,
        review_main=None,
        manual_main=None,
        unverified_receipt=False,
    )


def test_startup_schema_check_protects_against_recovery_migration_crash():
    source = (Path(__file__).resolve().parents[1] /
              "src/centermanager/app.py").read_text(encoding="utf-8")
    main = source.split("def main() -> int:", 1)[1]
    assert "use_readonly_schema = _requires_readonly_schema_for_recovery(" in main
    assert main.index("if use_readonly_schema:") < main.index("ensure_schema()")
    assert "verify_runtime_schema_readonly()" in main
    assert "record_verified_review_reset(" in main
    assert "receipt_seal_failed = True" in main
    assert "protect_read_only_for_process()" in main


def test_recovery_receipt_failure_latches_read_even_when_git_reconnects():
    with offline_read_state._lock:
        offline_read_state._recovery_read_only = False
        offline_read_state._offline_read = False
    try:
        offline_read_state.protect_read_only_for_process()
        assert offline_read_state.recovery_read_only_active()
        assert offline_read_state.offline_read_active()
        offline_read_state.set_offline_read(False)
        assert offline_read_state.offline_read_active()
    finally:
        with offline_read_state._lock:
            offline_read_state._recovery_read_only = False
            offline_read_state._offline_read = False


def test_review_skip_remains_pending_but_acknowledged_case_does_not_reappear(tmp_path):
    old = tmp_path / "runtime" / "Database" / "center.db"
    old.parent.mkdir(parents=True)
    old.write_bytes(b"unpublished SQLCipher test artifact")
    journal = tmp_path / "runtime.write-recovery" / "journal.json"
    journal.parent.mkdir(parents=True)
    journal.write_text('{"status":"OPEN","session_id":"forced-kill"}', encoding="utf-8")
    case = RecoveryReviewNotices(SimpleNamespace(
        root=journal.parent, journal=journal, runtime=tmp_path / "runtime"
    ))
    notice_path = case.record(observed_main_oid="a" * 40)
    notice = case.validate_notice(notice_path)
    assert notice["status"] == "PENDING_REVIEW"
    assert len(case.pending()) == 1       # Skip/close is NO mutation
    case.acknowledge(notice["id"])
    assert not case.pending()            # Reviewed only controls notification
    assert journal.read_text(encoding="utf-8") == (
        '{"status":"OPEN","session_id":"forced-kill"}'
    )
    assert old.read_bytes() == b"unpublished SQLCipher test artifact"


def test_notice_buttons_never_write_business_data():
    root = Path(__file__).resolve().parents[1] / "src/centermanager"
    ui = (root / "ui/main_window.py").read_text(encoding="utf-8")
    section = ui.split("def _show_pending_review_notices(", 1)[1].split(
        "def _show_pending_recovery_cases(", 1
    )[0]
    assert 'dialog.addButton("Đã kiểm tra"' in section
    assert 'dialog.addButton("Để lần sau"' in section
    assert "queue.acknowledge(item" in section
    assert "return  # Skip or close never acknowledges any event." in section
    assert "publish_only(" not in section
    assert "ensure_schema(" not in section


def test_background_reconnect_never_clears_failed_recovery_authority():
    root = Path(__file__).resolve().parents[1] / "src/centermanager"
    loop = (root / "platform/sync/runtime_sync_service.py").read_text(encoding="utf-8")
    promote = (root / "platform/sync/authoritative_runtime_sync_service.py").read_text(encoding="utf-8")
    assert "if recovery_read_only_active():" in loop
    assert "if recovery_read_only_active():" in promote
