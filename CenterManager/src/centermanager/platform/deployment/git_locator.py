# -*- coding: utf-8 -*-
"""Locate Git executable (portable or system)."""

import os
import sys
import shutil
from pathlib import Path
from typing import Optional

def locate_git() -> Optional[Path]:
    """
    Locate git executable.
    Priority:
      1. Portable git in {executable_dir}/git/cmd/git.exe or bin/git.exe
      2. System git from PATH
    Returns Path to git executable or None.
    """
    # Determine base directory (where executable or script is)
    if getattr(sys, 'frozen', False):
        base_dir = Path(sys.executable).resolve().parent
    else:
        # Running from source, use project root
        base_dir = Path(__file__).resolve().parent.parent.parent.parent.parent  # up to project root

    # Check portable git locations
    portable_paths = [
        base_dir / "git" / "cmd" / "git.exe",
        base_dir / "git" / "bin" / "git.exe",
        base_dir / "git" / "git.exe",
    ]
    if sys.platform == "win32":
        portable_paths.extend([
            base_dir / "git" / "cmd" / "git.exe",
            base_dir / "Git" / "cmd" / "git.exe",
        ])
    else:
        portable_paths.extend([
            base_dir / "git" / "bin" / "git",
            base_dir / "git" / "git",
        ])

    for p in portable_paths:
        if p.exists() and os.access(str(p), os.X_OK):
            return p

    # Fallback to system git
    system_git = shutil.which("git")
    if system_git:
        return Path(system_git)

    return None