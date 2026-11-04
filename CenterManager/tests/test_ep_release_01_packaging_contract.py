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
    assert 'VERSION_FILE = PROJECT_ROOT / "VERSION"' in source
    assert 'VERSION = read_release_version()' in source
    assert 'RELEASE_NAME = f"{APP_NAME}-v{VERSION}-windows-x64"' in source
    assert 'generate_windows_version_metadata' in source
    assert 'RELEASE_MANIFEST.json' in source
    assert 'README_RELEASE.md' in source
    assert 'UAT_CHECKLIST.md' in source
    assert 'shutil.make_archive(' in source
    assert 'write_archive_checksum' in source
    assert 'VERSION = "0.1.0-prototype"' not in source


def test_frozen_paths_keep_mutable_runtime_next_to_executable():
    source = (ROOT / "src/centermanager/core/paths.py").read_text(encoding="utf-8")
    assert "frozen" in source
    assert "sys.executable" in source
    assert 'Path(sys.executable).resolve().parent' in source
    assert 'self._runtime_root = self._project_root / "runtime"' in source


def test_release_entrypoint_remains_run_py():
    source = (ROOT / "run.py").read_text(encoding="utf-8")
    imports_app_entrypoint = (
        'from centermanager.app import main' in source
        or 'import centermanager.app as app_module' in source
    )
    assert imports_app_entrypoint
    assert 'sys.exit(main())' in source


def test_runtime_repository_is_not_a_gitlink():
    """The runtime template must not contain a stale nested-repository gitlink."""
    # Pathspecs are relative to cwd, so run from the CenterManager project root
    # where runtime/ actually lives.
    result = subprocess.run(
        ["git", "ls-files", "--stage", "--", "runtime"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "160000 " not in result.stdout


# TECH-002: only these runtime template files may be tracked; everything else
# under runtime/ is machine-local state (snapshots, attachments, heartbeats,
# config/secrets, nested repositories).
TRACKED_RUNTIME_TEMPLATE_FILES = {
    "runtime/collaboration/lock.json",
    "runtime/manifest.json",
    "runtime/metadata/version.json",
}


def test_runtime_tracks_only_template_files():
    result = subprocess.run(
        ["git", "ls-files", "--", "runtime"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    tracked = {line.strip() for line in result.stdout.splitlines() if line.strip()}
    assert tracked, "git ls-files returned nothing; test must run inside the repository checkout"
    assert tracked == TRACKED_RUNTIME_TEMPLATE_FILES


def test_runtime_directory_contract_is_shared_with_release_builder():
    from centermanager.core.paths import RUNTIME_REQUIRED_DIRS

    source = (ROOT / "build_release.py").read_text(encoding="utf-8")
    for directory in RUNTIME_REQUIRED_DIRS:
        assert f'"{directory}"' in source
