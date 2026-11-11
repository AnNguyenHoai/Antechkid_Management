"""Phase 3: Recovery receipts are advisory only for independently verified READ.

All destructive/authenticating gates remain fail-closed. This module tests
only the final application policy; it never opens a production database.
"""
from pathlib import Path
from types import SimpleNamespace

from centermanager.app import _degrade_startup_to_verified_read
from centermanager.platform.sync.offline_read_state import (
    offline_read_active, set_offline_read,
)


def test_receipt_error_explicitly_denies_write_and_marks_read_only():
    bootstrap = SimpleNamespace(_offline_read=False)
    provider = SimpleNamespace()
    set_offline_read(False)
    try:
        _degrade_startup_to_verified_read(bootstrap, provider, "test injected")
        assert bootstrap._offline_read is True
        assert offline_read_active() is True
        assert provider._startup_recovery_receipt_warning is True
    finally:
        set_offline_read(False)


def test_receipt_gate_only_runs_after_authenticated_bootstrap_and_schema():
    app = (Path(__file__).resolve().parents[1] /
           "src/centermanager/app.py").read_text(encoding="utf-8")
    assert app.index("if not bootstrap.run():") < app.index(
        "_degrade_startup_to_verified_read(", app.index("def main()")
    )
    assert "verify_runtime_schema_readonly()" in app
    assert "ensure_schema()" in app
    assert "record_verified_review_reset(" in app
    assert "record_verified_manual_reset(" in app
    assert "record_verified_fresh_install(" in app
    assert "refresh_verified_bootstrap_migration(" in app
    assert "and not bootstrap._offline_read" in app


def test_existing_write_transaction_revalidates_clean_receipt():
    root = Path(__file__).resolve().parents[1] / "src/centermanager"
    source = (root / "services/write_transaction.py").read_text(encoding="utf-8")
    assert "require_replaceable()" in source
    assert "journal.assert_replaceable()" in source
    collab = (root / "platform/collaboration/collaboration_manager.py").read_text(encoding="utf-8")
    assert "offline_read_active()" in collab
