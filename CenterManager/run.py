#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
import os
from pathlib import Path

# Ghi log lỗi ra file nếu chạy exe
if getattr(sys, 'frozen', False):
    log_file = Path(os.path.dirname(sys.executable)) / "error.log"
    sys.stderr = open(log_file, "w")
    sys.stdout = open(log_file, "a")

# Thêm src/ vào sys.path
src_path = Path(__file__).resolve().parent / "src"
if src_path.exists() and str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

from centermanager.app import main


def _portable_smoke_check() -> int:
    """Validate the frozen package without opening the full GUI."""
    from centermanager.core.git_locator import locate_git
    from centermanager.core.paths import get_paths
    import subprocess

    paths = get_paths()
    paths.ensure_directories()
    git_executable = locate_git()
    if git_executable is None:
        raise RuntimeError("Bundled Git was not found in the release package")
    result = subprocess.run(
        [str(git_executable), "--version"],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"Bundled Git smoke check failed: {result.stderr.strip()}"
        )
    print(f"Portable smoke check passed: {result.stdout.strip()}")
    print(f"Runtime root: {paths.runtime_root}")
    return 0


if __name__ == "__main__":
    if os.environ.get("CENTERMANAGER_PORTABLE_SMOKE") == "1":
        sys.exit(_portable_smoke_check())
    sys.exit(main())
