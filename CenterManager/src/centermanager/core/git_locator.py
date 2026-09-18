# -*- coding: utf-8 -*-
"""Resolve the Git executable for optional Git features."""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional


def locate_git() -> Optional[Path]:
    """Return bundled Git first, then system Git, or None when unavailable."""
    if getattr(sys, "frozen", False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        # Source layout: CenterManager/src/centermanager/core/git_locator.py
        base_dir = Path(__file__).resolve().parents[3]

    candidates = [
        base_dir / "git" / "cmd" / "git.exe",
        base_dir / "git" / "bin" / "git.exe",
        base_dir / "git" / "git.exe",
    ]
    if sys.platform == "win32":
        candidates.append(base_dir / "Git" / "cmd" / "git.exe")
    else:
        candidates.extend([
            base_dir / "git" / "bin" / "git",
            base_dir / "git" / "git",
        ])

    for candidate in candidates:
        if candidate.exists() and os.access(str(candidate), os.X_OK):
            return candidate

    system_git = shutil.which("git")
    return Path(system_git) if system_git else None
