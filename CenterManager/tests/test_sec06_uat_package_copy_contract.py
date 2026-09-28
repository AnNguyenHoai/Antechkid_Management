from pathlib import Path


def test_fixture_mutates_only_copied_package():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    copy = script.index("shutil.copytree(package, target)")
    cleanup = script.index('for relative in ("runtime/Database", "runtime/repository", "runtime/Config")')
    assert copy < cleanup
