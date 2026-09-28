from pathlib import Path


def test_restore_preservation_is_inside_rollback_boundary():
    source = Path("src/centermanager/platform/backup/backup_service.py").read_text(encoding="utf-8")
    preserve_comment = "All live mutations, including preservation, participate in one"
    assert preserve_comment in source
    assert "for live, preserved in reversed(preserved_sidecars):" in source
