from pathlib import Path


def test_uat_fixture_requires_new_target_and_remote():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert "if target.exists() or remote.exists():" in script
    assert "Target workspace and local remote must not already exist" in script
    assert "Place UAT target/remote outside the CenterManager source tree" in script
