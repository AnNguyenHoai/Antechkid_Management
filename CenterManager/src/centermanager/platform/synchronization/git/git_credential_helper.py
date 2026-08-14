# -*- coding: utf-8 -*-
"""GitCredentialHelper - Non-interactive Git authentication using GIT_ASKPASS."""

import os
import sys
import tempfile
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class GitCredentialHelper:
    """
    Provides non-interactive Git authentication via GIT_ASKPASS script.
    Token is supplied to Git without user interaction.
    """

    def __init__(self, username: str, token: str):
        self._username = username
        self._token = token
        self._askpass_path: Optional[Path] = None

    def setup_environment(self) -> dict:
        """Return environment variables for Git authentication."""
        if self._askpass_path is None:
            self._askpass_path = self._create_askpass_script()
        return {
            "GIT_ASKPASS": str(self._askpass_path),
        }

    def _create_askpass_script(self) -> Path:
        """Create temporary askpass script that returns the token for any prompt."""
        if sys.platform == "win32":
            # On Windows, use a batch script
            content = f'''@echo off
echo {self._token}
'''
            suffix = '.bat'
        else:
            content = f'''#!/bin/sh
echo "{self._token}"
'''
            suffix = '.sh'

        fd, path = tempfile.mkstemp(suffix=suffix, prefix='git-askpass-', text=True)
        with os.fdopen(fd, 'w') as f:
            f.write(content)

        if sys.platform != "win32":
            os.chmod(path, 0o700)

        logger.debug(f"Created askpass script: {path}")
        return Path(path)

    def cleanup(self) -> None:
        """Remove temporary askpass script."""
        if self._askpass_path and self._askpass_path.exists():
            try:
                self._askpass_path.unlink()
                logger.debug(f"Removed askpass script: {self._askpass_path}")
            except Exception as e:
                logger.warning(f"Failed to remove askpass script: {e}")

    def __del__(self):
        self.cleanup()