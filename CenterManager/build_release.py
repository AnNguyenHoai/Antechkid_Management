#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the CenterManager Windows prototype release."""

import os
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
    "backup", "Backup", "repository", ".git", "__pycache__",
    "attachments", "Attachments", "Attachment",
)


def _remove_tree(path: Path) -> None:
    """Remove a generated tree and handle Windows read-only files safely."""
    def _on_rm_error(func, target, exc_info):
        try:
            os.chmod(target, 0o700)
            func(target)
        except OSError:
            raise
    shutil.rmtree(path, onerror=_on_rm_error)


def clean_outputs() -> None:
    """Remove generated build/release directories only."""
    for path in (DIST_ROOT, PROJECT_ROOT / "build", RELEASE_ROOT):
        if path.exists():
            try:
                _remove_tree(path)
            except PermissionError as exc:
                raise PermissionError(
                    f"Cannot clean release output '{path}'. "
                    "Close CenterManager.exe, Git clients, terminals, or other "
                    "processes using files under this directory, then run "
                    "build_release.py again."
                ) from exc


def copy_runtime_template() -> None:
    """Copy immutable runtime assets and materialize the canonical contract."""
    src_runtime = PROJECT_ROOT / "runtime"
    dst_runtime = PACKAGE_ROOT / "runtime"
    if not src_runtime.exists():
        raise FileNotFoundError(f"Runtime template not found: {src_runtime}")
    shutil.copytree(src_runtime, dst_runtime, ignore=RUNTIME_EXCLUDES)

    for dir_name in (
        "Database", "Export", "Attachment", "Config", "Backup", "Logs",
        "Reports", "Temp", "metadata", "collaboration", "snapshots",
    ):
        (dst_runtime / dir_name).mkdir(parents=True, exist_ok=True)


def copy_migration_assets() -> None:
    """Ship Alembic assets beside the portable executable for frozen startup."""
    for name in ("alembic.ini", "migrations"):
        source = PROJECT_ROOT / name
        target = PACKAGE_ROOT / name
        if not source.exists():
            raise FileNotFoundError(f"Required migration asset not found: {source}")
        if source.is_dir():
            shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
        else:
            shutil.copy2(source, target)


def write_release_readme() -> None:
    (PACKAGE_ROOT / "README_RELEASE.md").write_text(
        f"# CenterManager {VERSION}\n\n"
        "Windows prototype release.\n\n"
        "## Start\n\n"
        "Run CenterManager.exe. Mutable application data is stored in the runtime folder beside the executable.\n\n"
        "## Important\n\n"
        "- Do not delete or rename the runtime folder.\n"
        "- Configure Git synchronization on first launch when requested.\n"
        "- Use the application's backup flow for test data.\n"
        "- Alembic migration assets are shipped with the release and are required for startup.\n"
        "- If startup fails, inspect error.log beside the executable and runtime/Logs/.\n",
        encoding="utf-8",
    )


def write_uat_checklist() -> None:
    (PACKAGE_ROOT / "UAT_CHECKLIST.md").write_text(
        "# CenterManager Prototype UAT Checklist\n\n"
        "- [ ] Launch CenterManager.exe from a clean Windows user directory.\n"
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
        "- [ ] No source checkout or Python installation is required to launch.\n",
        encoding="utf-8",
    )


def build_executable() -> Path:
    """Build the one-file, windowed executable."""
    args = [
        "run.py", "--name", APP_NAME, "--onefile", "--windowed",
        "--paths", str(PROJECT_ROOT / "src"),
        "--version-file", str(PROJECT_ROOT / "version_metadata.txt"),
        "--add-data", f"{PROJECT_ROOT / 'alembic.ini'}{os.pathsep}.",
        "--add-data", f"{PROJECT_ROOT / 'migrations'}{os.pathsep}migrations",
    ]
    hidden_imports = [
        "centermanager", "centermanager.core", "centermanager.database",
        "centermanager.models", "centermanager.repositories",
        "centermanager.services", "centermanager.ui", "centermanager.export",
        "centermanager.platform", "centermanager.events", "alembic",
        "sqlalchemy", "openpyxl", "reportlab", "bcrypt", "git", "PySide6",
        "logging.config",
    ]
    for module in hidden_imports:
        args.extend(["--hidden-import", module])
    PyInstaller.__main__.run(args)
    executable = DIST_ROOT / f"{APP_NAME}.exe"
    if not executable.exists():
        raise FileNotFoundError(f"PyInstaller did not create {executable}")
    return executable


def create_release_package(executable: Path) -> Path:
    """Assemble the portable release directory and ZIP archive."""
    PACKAGE_ROOT.mkdir(parents=True, exist_ok=True)
    shutil.copy2(executable, PACKAGE_ROOT / executable.name)
    copy_runtime_template()
    copy_migration_assets()
    write_release_readme()
    write_uat_checklist()
    archive = shutil.make_archive(
        str(RELEASE_ROOT / RELEASE_NAME), "zip",
        root_dir=RELEASE_ROOT, base_dir=RELEASE_NAME,
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
