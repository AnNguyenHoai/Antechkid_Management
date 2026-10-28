from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_profile_image_change_publishes_student_updated():
    t = read("src/centermanager/services/student_service.py")
    assert "StudentUpdated event published for profile image change" in t

def test_pdf_uses_attachment_directory_for_relative_profile_path():
    t = read("src/centermanager/export/pdf/student_report_generator.py")
    assert "get_paths().attachment_dir / image_path" in t

def test_snapshot_deleted_only_after_confirmed_lock_release():
    t = read("src/centermanager/services/write_transaction.py")
    assert "def _delete_snapshot(self)" in t

    publish_start = t.index("    def _publish(self)")
    publish_end = t.index("    def _do_publish", publish_start)
    publish_block = t[publish_start:publish_end]

    assert "if not self._release_lock():" in publish_block
    assert "WriteTransactionState.PUBLISHED_LOCK_RELEASE_PENDING" in publish_block

    pending_marker = publish_block.index(
        "WriteTransactionState.PUBLISHED_LOCK_RELEASE_PENDING"
    )
    delete_marker = publish_block.index("self._delete_snapshot()", pending_marker)
    reset_marker = publish_block.index("self._reset_to_idle()", delete_marker)
    assert pending_marker < delete_marker < reset_marker

    retry_start = t.index("    def retry_lock_release(self)")
    retry_end = t.index("    # ---- Retry / Offline", retry_start)
    retry_block = t[retry_start:retry_end]
    assert "if not self._release_lock():" in retry_block
    assert "self._delete_snapshot()" in retry_block
    assert "self._reset_to_idle()" in retry_block

def test_snapshot_deleted_after_cancel():
    t = read("src/centermanager/services/write_transaction.py")
    cancel_start = t.index("    def cancel_editing")
    cancel_end = t.index("    # ---- Publish helpers", cancel_start)
    cancel_block = t[cancel_start:cancel_end]

    delete_marker = cancel_block.index("self._delete_snapshot()")
    reset_marker = cancel_block.index("self._reset_to_idle()", delete_marker)
    assert delete_marker < reset_marker
