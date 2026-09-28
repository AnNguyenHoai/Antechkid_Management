from pathlib import Path


def test_uat_fixture_commits_database_identity_and_manifest_together():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    add_pos = script.index('"database/center.db"')
    identity_pos = script.index('"database/center.db.identity.json"')
    manifest_pos = script.index("manifest.name")
    commit_pos = script.index('"commit", "-m", "SEC06 isolated UAT generation 1"')
    assert add_pos < commit_pos
    assert identity_pos < commit_pos
    assert manifest_pos < commit_pos
