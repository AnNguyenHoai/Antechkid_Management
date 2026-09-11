#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Build script for CenterManager release packaging.
Generates a standalone executable with bundled runtime and Git.

Usage:
    python build_release.py

Output: dist/CenterManager/
"""

import os
import shutil
import sys
from pathlib import Path
import PyInstaller.__main__

PROJECT_ROOT = Path(__file__).resolve().parent
VERSION = "1.0.0"
APP_NAME = "CenterManager"


def clean_dist():
    """Remove previous build artifacts."""
    for dir_name in ["dist", "build"]:
        dir_path = PROJECT_ROOT / dir_name
        if dir_path.exists():
            shutil.rmtree(dir_path)


def copy_runtime_and_config():
    """Copy runtime/ (with metadata) and config/ into dist."""
    dist_root = PROJECT_ROOT / "dist" / APP_NAME

    # Copy runtime
    src_runtime = PROJECT_ROOT / "runtime"
    dst_runtime = dist_root / "runtime"
    if dst_runtime.exists():
        shutil.rmtree(dst_runtime)
    shutil.copytree(src_runtime, dst_runtime, ignore=shutil.ignore_patterns(
        "*.db", "*.db-journal", "logs", "cache", "temp", "backup"
    ))

    # Create config folder for user settings (optional)
    (dist_root / "config").mkdir(exist_ok=True)

    # Copy portable Git if present
    git_src = PROJECT_ROOT / "git"
    if git_src.exists():
        git_dst = dist_root / "git"
        if git_dst.exists():
            shutil.rmtree(git_dst)
        shutil.copytree(git_src, git_dst)


def build():
    """Run PyInstaller."""
    clean_dist()
    print("Building CenterManager...")

    args = [
        "run.py",
        "--name", APP_NAME,
        "--onefile",   # thay vì --onefile
        "--windowed",
        "--add-data", f"runtime{os.pathsep}runtime",
        "--paths", str(PROJECT_ROOT / "src"),
    ]

    # Add git data if portable git exists
    if (PROJECT_ROOT / "git").exists():
        args.extend(["--add-data", f"git{os.pathsep}git"])

    # Hidden imports
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
        "alembic",
        "sqlalchemy",
        "openpyxl",
        "reportlab",
        "pyside6",
    ]
    for mod in hidden_imports:
        args.extend(["--hidden-import", mod])

    # Version file
    version_file = PROJECT_ROOT / "version_metadata.txt"
    if version_file.exists():
        args.extend(["--version-file", str(version_file)])

    print(f"PyInstaller arguments: {args}")
    PyInstaller.__main__.run(args)

    # After build, copy runtime and git
    copy_runtime_and_config()

    print(f"Build complete. Executable is in: dist/{APP_NAME}/")
    size_mb = sum(f.stat().st_size for f in (PROJECT_ROOT / "dist" / APP_NAME).rglob('*')) / (1024 * 1024)
    print(f"Size: {size_mb:.1f} MB")


def main():
    build()


if __name__ == "__main__":
    main()