from pathlib import Path


def test_restore_refreshes_runtime_sessions_after_file_replacement():
    source = Path("src/centermanager/platform/backup/backup_service.py").read_text(encoding="utf-8")
    assert "os.replace(db_tmp, paths.database_dir / \"center.db\")" in source
    assert "refresh_runtime_db()" in source


def test_backup_runtime_contract_includes_integrity_and_checksum_validation():
    source = Path("src/centermanager/platform/backup/backup_service.py").read_text(encoding="utf-8")
    assert "PRAGMA integrity_check" in source
    assert "Database checksum mismatch" in source
    assert "Backup path is outside the managed backup directory" in source
