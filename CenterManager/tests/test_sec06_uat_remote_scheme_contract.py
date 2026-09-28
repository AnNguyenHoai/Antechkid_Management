from pathlib import Path


def test_fixture_repository_url_is_derived_from_local_path():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert '"repository_url": remote.as_uri()' in script
    assert "https://" not in script
    assert "ssh://" not in script
