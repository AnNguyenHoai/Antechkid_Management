from pathlib import Path


def test_fixture_requires_center_manager_executable():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert '(source / "CenterManager.exe").is_file()' in script
