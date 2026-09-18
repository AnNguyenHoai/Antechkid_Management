"""A4.4 release-candidate packaging contracts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "build_release.py"
WORKFLOW = ROOT.parent / ".github" / "workflows" / "windows-prototype-release.yml"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_release_excludes_mutable_database_and_development_artifacts():
    source = _read(BUILDER)
    for pattern in (
        '"*.db"',
        '"*.sqlite"',
        '"*.sqlite3"',
        '"repository"',
        '".git"',
        '"__pycache__"',
        '"*.pyc"',
        '"*.log"',
        '"*.tmp"',
        '"*.bak"',
    ):
        assert pattern in source


def test_release_contains_required_runtime_and_migration_assets():
    source = _read(BUILDER)
    assert '("alembic.ini", "migrations")' in source
    for directory in (
        '"Database"', '"Export"', '"Attachment"', '"Config"', '"Backup"',
        '"Logs"', '"Reports"', '"Temp"', '"metadata"', '"collaboration"', '"snapshots"',
    ):
        assert directory in source


def test_release_bundles_pinned_git_and_verifies_checksum():
    source = _read(BUILDER)
    assert 'PORTABLE_GIT_VERSION = "2.54.0"' in source
    assert "PORTABLE_GIT_URL" in source
    assert "PORTABLE_GIT_SHA256" in source
    assert "hashlib.sha256()" in source
    assert 'target / "cmd" / "git.exe"' in source


def test_release_readme_matches_git_authoritative_startup_contract():
    source = _read(BUILDER)
    assert "Git repository database is authoritative" in source
    assert "startup refuses to use a stale local database" in source


def test_clean_machine_workflow_rejects_python_source_and_git_metadata():
    source = _read(WORKFLOW)
    assert '"python.exe", "pythonw.exe"' in source
    assert '"\\src\\|\\.git\\"' in source
    assert "Clean-machine portable smoke test" in source
    assert "SystemRoot}\\System32" in source


def test_clean_machine_workflow_verifies_executable_and_bundled_git():
    source = _read(WORKFLOW)
    assert 'Test-Path $exe' in source
    assert 'Test-Path $git' in source
    assert "& $git --version" in source
    assert "CENTERMANAGER_PORTABLE_SMOKE" in source


def test_release_does_not_ship_a_database():
    source = _read(BUILDER)
    start = source.index("def copy_runtime_template")
    end = source.index("def copy_migration_assets", start)
    block = source[start:end]
    assert "RUNTIME_EXCLUDES" in source
    assert "copytree" in block


def test_uat_checklist_covers_two_machine_and_restart_proof():
    source = _read(BUILDER)
    assert "second machine" in source
    assert "Restarting the executable" in source
    assert "stale local database" in source
