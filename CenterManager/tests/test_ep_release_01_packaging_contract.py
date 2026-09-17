from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_script_produces_external_runtime_package():
    source = (ROOT / "build_release.py").read_text(encoding="utf-8")
    assert '"--onefile"' in source
    assert '"--windowed"' in source
    assert 'RUNTIME_EXCLUDES = shutil.ignore_patterns(' in source
    for excluded in ("*.db", "*.db-journal", "*.db-wal", "*.db-shm", "*.sqlite", "*.sqlite3"):
        assert excluded in source
    assert 'PACKAGE_ROOT / "runtime"' in source


def test_release_script_has_portable_release_metadata_and_archive():
    source = (ROOT / "build_release.py").read_text(encoding="utf-8")
    assert 'VERSION = "0.1.0-prototype"' in source
    assert 'RELEASE_NAME = f"{APP_NAME}-v{VERSION}-windows-x64"' in source
    assert 'README_RELEASE.md' in source
    assert 'UAT_CHECKLIST.md' in source
    assert 'shutil.make_archive(' in source


def test_frozen_paths_keep_mutable_runtime_next_to_executable():
    source = (ROOT / "src/centermanager/core/paths.py").read_text(encoding="utf-8")
    assert 'getattr(sys, \'frozen\', False)' in source
    assert 'Path(sys.executable).resolve().parent' in source
    assert 'self._runtime_root = self._project_root / "runtime"' in source


def test_release_entrypoint_remains_run_py():
    source = (ROOT / "run.py").read_text(encoding="utf-8")
    assert 'from centermanager.app import main' in source
    assert 'sys.exit(main())' in source
