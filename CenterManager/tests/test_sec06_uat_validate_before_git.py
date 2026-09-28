from pathlib import Path


def test_authoritative_pair_is_validated_before_git_initialization():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    validate = script.index("validate_authoritative_repository_database()")
    git_init = script.index('_git("init", "-b", "main", cwd=repo)')
    assert validate < git_init
