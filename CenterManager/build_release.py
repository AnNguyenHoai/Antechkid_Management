#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the CenterManager Windows prototype release.

The application is packaged as a one-file PyInstaller executable while the
mutable ``runtime/`` directory stays beside the executable. Alembic migration
assets remain external beside the executable as immutable release resources.
Runtime data must never be embedded into the executable.

Usage:
    python build_release.py

Output:
    release/CenterManager-v0.1.0-prototype-windows-x64/
    release/CenterManager-v0.1.0-prototype-windows-x64.zip
"""

import shutil
from pathlib import Path

import PyInstaller.__main__

PROJECT_ROOT = Path(__file__).resolve().parent
VERSION = "0.1.0-prototype"
APP_NAME = "CenterManager"
RELEASE_NAME = f"{APP_NAME}-v{VERSION}-windows-x64"
DIST_ROOT = PROJECT_ROOT / "dist"
RELEASE_ROOT = PROJECT_ROOT / "release"
PACKAGE_ROOT = RELEASE_ROOT / RELEASE_NAME

RUNTIME_EXCLUDES = shutil.ignore_patterns(
    "*.db", "*.db-journal", "*.db-wal", "*.db-shm",
    "*.sqlite", "*.sqlite3",
    "logs", "Logs", "cache", "Cache", "temp", "Temp",
    "backup", "Backup",
)


def clean_outputs() -> None:
    """Remove generated build/release directories only."""
    for path in (DIST_ROOT, PROJECT_ROOT / "build", RELEASE_ROOT):
        if path.exists():
            shutil.rmtree(path)


def copy_runtime_template(destination_root: Path) -> None:
    """Copy only the immutable runtime template; never ship live DB/backups."""
    src_runtime = PROJECT_ROOT / "runtime"
    dst_runtime = destination_root / "runtime"
    if not src_runtime.exists():
        raise FileNotFoundError(f"Runtime template not found: {src_runtime}")
    shutil.copytree(src_runtime, dst_runtime, ignore=RUNTIME_EXCLUDES)


def copy_migration_assets(destination_root: Path) -> None:
    """Copy immutable Alembic assets beside the executable."""
    src_migrations = PROJECT_ROOT / "migrations"
    dst_migrations = destination_root / "migrations"
    src_alembic_ini = PROJECT_ROOT / "alembic.ini"
    if not src_migrations.exists():
        raise FileNotFoundError(f"Migration directory not found: {src_migrations}")
    if not src_alembic_ini.exists():
        raise FileNotFoundError(f"Alembic config not found: {src_alembic_ini}")
    shutil.copytree(src_migrations, dst_migrations)
    shutil.copy2(src_alembic_ini, destination_root / "alembic.ini")


def stage_intermediate_dist(executable: Path) -> None:
    """Keep the freshly built ``dist/CenterManager.exe`` directly runnable.

    This is a developer/build smoke-test convenience; the distributable
    package is assembled separately under ``release/``.
    """
    copy_runtime_template(DIST_ROOT)
    copy_migration_assets(DIST_ROOT)


def write_release_readme() -> None:
    (PACKAGE_ROOT / "README_RELEASE.md").write_text(
        f"# CenterManager {VERSION}\n\n"
        "Windows prototype release.\n\n"
        "## Start\n\n"
        "Run `CenterManager.exe`. Mutable application data is stored in the `runtime/` folder beside the executable. Alembic migration assets are stored in the `migrations/` folder beside the executable.\n\n"
        "## Important\n\n"
        "- Do not delete or rename the `runtime/` or `migrations/` folders.\n"
        "- Keep `alembic.ini` beside `CenterManager.exe`.\n"
        "- Configure Git synchronization on first launch when requested.\n"
        "- Use the application's backup flow for test data.\n"
        "- If startup fails, inspect `error.log` beside the executable and `runtime/Logs/`.\n",
        encoding="utf-8",
    )


def write_uat_checklist() -> None:
    (PACKAGE_ROOT / "UAT_CHECKLIST.md").write_text(
        "# CenterManager Prototype UAT Checklist\n\n"
        "- [ ] Launch `CenterManager.exe` from a clean Windows user directory.\n"
        "- [ ] Complete first-run configuration.\n"
        "- [ ] Login succeeds with the test account.\n"
        "- [ ] Student workspace and navigation work.\n"
        "- [ ] Class and Teacher workspaces open.\n"
        "- [ ] Session / Attendance / Assessment flows open.\n"
        "- [ ] Finance workspace opens.\n"
        "- [ ] Student Timeline opens.\n"
        "- [ ] Export/report actions produce expected files.\n"
        "- [ ] Backup/restore can be exercised with test data.\n"
        "- [ ] Restarting the executable preserves expected runtime data.\n"
        "- [ ] No source checkout or Python installation is required to launch.\n"
        "- [ ] `migrations/` and `alembic.ini` remain beside the executable.\n",
        encoding="utf-8",
    )


def build_executable() -> Path:
    """Build the one-file, windowed executable."""
    args = [
        "run.py",
        "--name", APP_NAME,
        "--onefile",
        "--windowed",
        "--paths", str(PROJECT_ROOT / "src"),
        "--version-file", str(PROJECT_ROOT / "version_metadata.txt"),
    ]

    hidden_imports = [
        "centermanager",
        "centermanager.core",
        "centermanager.database",
        "centermanager.models",
        "centermanager.repositories",
        "centermanager.services",
        "centermanager.ui",
        "centermanager.export",
        "centermanager.platform",
        "centermanager.events",
        "alembic",
        "sqlalchemy",
        "openpyxl",
        "reportlab",
        "bcrypt",
        "git",
        "PySide6",
    ]
    for module in hidden_imports:
        args.extend(["--hidden-import", module])

    PyInstaller.__main__.run(args)
    executable = DIST_ROOT / f"{APP_NAME}.exe"
    if not executable.exists():
        raise FileNotFoundError(f"PyInstaller did not create {executable}")
    stage_intermediate_dist(executable)
    return executable


def create_release_package(executable: Path) -> Path:
    """Assemble the portable release directory and ZIP archive."""
    PACKAGE_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, PACKAGE_ROOT / executable.name)
    copy_runtime_template(PACKAGE_ROOT)
    copy_migration_assets(PACKAGE_ROOT)
    write_release_readme()
    write_uat_checklist()

    archive = shutil.make_archive(
        str(RELEASE_ROOT / RELEASE_NAME),
        "zip",
        root_dir=RELEASE_ROOT,
        base_dir=RELEASE_NAME,
    )
    return Path(archive)


def main() -> None:
    clean_outputs()
    print(f"Building {APP_NAME} {VERSION}...")
    executable = build_executable()
    archive = create_release_package(executable)
    size_mb = archive.stat().st_size / (1024 * 1024)
    print(f"Release package: {archive}")
    print(f"ZIP size: {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
