from pathlib import Path


def test_uat_fixture_forces_production_encryption_and_rejects_plaintext():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert 'os.environ["ANTECHKIDS_DEPLOYMENT_PROFILE"] = "production"' in script
    assert 'os.environ["ANTECHKIDS_FORCE_DATABASE_ENCRYPTION"] = "1"' in script
    assert "is_plaintext_sqlite_file(db)" in script
    assert "validate_authoritative_repository_database()" in script
