from pathlib import Path


def test_fixture_pushes_initial_main_and_sets_upstream():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert '_git("push", "-u", "origin", "main", cwd=repo)' in script
