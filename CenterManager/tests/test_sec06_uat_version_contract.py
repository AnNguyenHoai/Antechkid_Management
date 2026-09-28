from pathlib import Path


def test_generation_one_manifest_and_commit_are_aligned():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    assert '"runtime_version": 1' in script
    assert "SEC06 isolated UAT generation 1" in script
