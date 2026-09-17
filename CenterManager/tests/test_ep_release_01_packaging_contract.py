from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_script_produces_external_runtime_package():
    source = (ROOT / "build_release.py").read_text(encoding="utf-8")
    assert '"--onefile"' in source
    assert '"--windowed"' in source
    assert 'RUNTIME_EXCLUDES = shutil.ignore_patterns(' in source
    for excluded in ("*.db", "*.db-journal", "*.db-wal", "*.db-shm", "*.sqlite", "*.sqlite3"):
        assert excluded in source
    assert 'destination_root / "runtime"' in source


def test_release_script_copies_external_alembic_assets():
    source = (ROOT / "build_release.py").read_text(encoding="utf-8")
    assert 'src_migrations = PROJECT_ROOT / "migrations"' in source
    assert 'dst_migrations = destination_root / "migrations"' in source
    assert 'shutil.copytree(src_migrations, dst_migrations)' in source
    assert 'shutil.copy2(src_alembic_ini, destination_root / "alembic.ini")' in source
    assert 'copy_migration_assets(PACKAGE_ROOT)' in source
    assert 'stage_intermediate_dist(DIST_ROOT)' in source


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


def test_migration_config_uses_frozen_project_root():
    source = (ROOT / "src/centermanager/database/migration.py").read_text(encoding="utf-8")
    assert 'project_root = get_paths().project_root' in source
    assert 'project_root / "alembic.ini"' in source
    assert 'project_root / "migrations"' in source
    assert 'config.set_main_option("script_location", str(project_root / "migrations"))' in source


def test_release_entrypoint_remains_run_py():
    source = (ROOT / "run.py").read_text(encoding="utf-8")
    assert 'from centermanager.app import main' in source
    assert 'sys.exit(main())' in source
