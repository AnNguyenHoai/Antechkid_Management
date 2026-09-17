from pathlib import Path


def test_release_build_does_not_ship_live_runtime_databases_or_backups():
    source = Path("build_release.py").read_text(encoding="utf-8")
    for excluded in ("*.db", "*.db-journal", "backup"):
        assert excluded in source


def test_release_build_has_explicit_runtime_and_dependency_paths():
    source = Path("build_release.py").read_text(encoding="utf-8")
    assert '"--paths", str(PROJECT_ROOT / "src")' in source
    assert '"centermanager.services"' in source
    assert '"centermanager.platform"' in source
