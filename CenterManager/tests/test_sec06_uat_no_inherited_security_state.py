from pathlib import Path


def test_uat_fixture_does_not_reuse_release_database_key_or_repository():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert '"runtime/Database"' in script
    assert '"runtime/repository"' in script
    assert '"runtime/Config"' in script
    assert "shutil.rmtree(path)" in script
