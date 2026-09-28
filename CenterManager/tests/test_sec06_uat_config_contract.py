from pathlib import Path


def test_uat_fixture_writes_encrypted_local_git_configuration():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert "encrypt_git_config(json.dumps(git_config))" in script
    assert '"repository_url": remote.as_uri()' in script
    assert 'target / "runtime" / "Config" / "config.json"' in script
