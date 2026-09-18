# -*- coding: utf-8 -*-
"""GitCredentialHelper - Non-interactive Git authentication using GIT_ASKPASS."""

import logging
import os
import sys
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_USERNAME_ENV = "CENTERMANAGER_GIT_USERNAME"
_TOKEN_ENV = "CENTERMANAGER_GIT_TOKEN"


class GitCredentialHelper:
    """Provide Git credentials without placing secrets in process argv or scripts."""

    def __init__(self, username: str, token: str):
        self._username = username or "git"
        self._token = token
        self._askpass_path: Optional[Path] = None

    def setup_environment(self) -> dict:
        """Return environment variables for a non-interactive Git child process."""
        if self._askpass_path is None:
            self._askpass_path = self._create_askpass_script()
        return {
            "GIT_ASKPASS": str(self._askpass_path),
            "GIT_TERMINAL_PROMPT": "0",
            _USERNAME_ENV: self._username,
            _TOKEN_ENV: self._token,
        }

    def _create_askpass_script(self) -> Path:
        """Create a secret-free helper that reads credentials from child env vars."""
        if sys.platform == "win32":
            content = r'''@echo off
set "prompt=%~1"
echo %prompt% | %SystemRoot%\System32\findstr.exe /I "username" >nul
if %errorlevel%==0 (
  echo %CENTERMANAGER_GIT_USERNAME%
) else (
  echo %CENTERMANAGER_GIT_TOKEN%
)
'''
            suffix = ".bat"
        else:
            content = '''#!/bin/sh
case "$1" in
  *Username*|*username*) printf '%s\\n' "$CENTERMANAGER_GIT_USERNAME" ;;
  *) printf '%s\\n' "$CENTERMANAGER_GIT_TOKEN" ;;
esac
'''
            suffix = ".sh"

        fd, path = tempfile.mkstemp(suffix=suffix, prefix="git-askpass-", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)

        if sys.platform != "win32":
            os.chmod(path, 0o700)

        logger.debug("Created secret-free askpass helper")
        return Path(path)

    def cleanup(self) -> None:
        """Remove the temporary askpass helper."""
        if self._askpass_path and self._askpass_path.exists():
            try:
                self._askpass_path.unlink()
                logger.debug("Removed askpass helper")
            except Exception as exc:
                logger.warning("Failed to remove askpass helper: %s", exc)
        self._askpass_path = None

    def __del__(self):
        self.cleanup()
