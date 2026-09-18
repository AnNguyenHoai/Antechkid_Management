from pathlib import Path
import subprocess


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
    assert 'frozen' in source\n    assert 'sys.executable' in source
    assert 'Path(sys.executable).resolve().parent' in source
    assert 'self._runtime_root = self._project_root / "runtime"' in source


def test_release_entrypoint_remains_run_py():
    source = (ROOT / "run.py").read_text(encoding="utf-8")
    assert 'from centermanager.app import main' in source
    assert 'sys.exit(main())' in source


def test_runtime_repository_is_not_a_gitlink():
    """The runtime template must not contain a stale nested-repository gitlink.

    A gitlink without a matching .gitmodules entry breaks clean checkouts and
    can trigger fatal submodule cleanup errors in CI. The application creates
    the runtime repository when Git collaboration is configured, so the source
    tree must not carry a nested repository pointer.
    """
    repo_root = ROOT.parent
    result = subprocess.run(
        ["git", "ls-files", "--stage", "--", "runtime/repository"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "160000 " not in result.stdout


def test_runtime_directory_contract_is_shared_with_release_builder():
    from centermanager.core.paths import RUNTIME_REQUIRED_DIRS

    source = (ROOT / "build_release.py").read_text(encoding="utf-8")
    for directory in RUNTIME_REQUIRED_DIRS:
        assert f'"{directory}"' in source
