from pathlib import Path


def test_sec06_uat_harness_uses_only_local_file_remote():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert "remote.as_uri()" in script
    assert '"repository_url": remote.as_uri()' in script
    assert "github.com" not in script.lower()
