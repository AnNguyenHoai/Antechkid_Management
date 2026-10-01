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

def test_snapshot_deleted_after_successful_publish():
    t = read("src/centermanager/services/write_transaction.py")
    assert "def _delete_snapshot(self)" in t
    assert "self._release_lock()\n                self._delete_snapshot()\n                self._reset_to_idle()" in t

def test_snapshot_deleted_after_cancel():
    t = read("src/centermanager/services/write_transaction.py")
    cancel_start = t.index("    def cancel_editing")
    cancel_end = t.index("    # ---- Publish helpers", cancel_start)
    cancel_block = t[cancel_start:cancel_end]

    delete_marker = cancel_block.index("self._delete_snapshot()")
    reset_marker = cancel_block.index("self._reset_to_idle()", delete_marker)
    assert delete_marker < reset_marker
