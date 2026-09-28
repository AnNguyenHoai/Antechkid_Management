from pathlib import Path


def test_local_remote_is_created_after_first_authoritative_commit():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    commit = script.index('"commit", "-m", "SEC06 isolated UAT generation 1"')
    bare = script.index('"init", "--bare", str(remote)')
    push = script.index('"push", "-u", "origin", "main"')
    assert commit < bare < push
