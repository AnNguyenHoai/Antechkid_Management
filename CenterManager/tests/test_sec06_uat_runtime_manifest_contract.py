from pathlib import Path


def test_manifest_is_written_before_initial_git_commit():
    script = (
        Path(__file__).resolve().parents[1]
        / "scripts"
        / "prepare_sec06_isolated_uat.py"
    ).read_text(encoding="utf-8")

    load_manifest = script.index("canonical_manifest = _load_canonical_package_manifest(package)")
    write_manifest = script.index(
        "manifest = _write_initial_repository_manifest(repo, canonical_manifest)"
    )
    commit = script.index('"commit", "-m", "SEC06 isolated UAT generation 1"')

    assert load_manifest < write_manifest < commit
