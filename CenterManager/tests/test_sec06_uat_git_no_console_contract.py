from pathlib import Path


def test_uat_git_commands_use_no_window_flag():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert 'creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)' in script
