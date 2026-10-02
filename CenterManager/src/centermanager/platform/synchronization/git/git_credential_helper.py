# -*- coding: utf-8 -*-
"""GitCredentialHelper - non-interactive Git authentication helpers."""

import base64
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
    """Provide Git credentials without placing secrets in process argv or scripts.

    Windows GUI builds deliberately avoid ``GIT_ASKPASS`` because invoking a
    batch helper causes Git to create ``cmd.exe`` child processes which can
    flash a console window.  The provider consumes :meth:`http_auth_header`
    instead and injects it through Git's per-process configuration environment.
    Non-Windows platforms retain the existing secret-free askpass helper.
    """

    def __init__(self, username: str, token: str):
        self._username = username or "git"
        self._token = token
        self._askpass_path: Optional[Path] = None

    def setup_environment(self) -> dict:
        """Return environment variables for a non-interactive Git child process."""
        if sys.platform == "win32":
            # Do not create a .bat helper. Git will receive HTTPS credentials
            # through GIT_CONFIG_* in GitSynchronizationProvider._get_env().
            return {"GIT_TERMINAL_PROMPT": "0"}

        if self._askpass_path is None:
            self._askpass_path = self._create_askpass_script()
        return {
            "GIT_ASKPASS": str(self._askpass_path),
            "GIT_TERMINAL_PROMPT": "0",
            _USERNAME_ENV: self._username,
            _TOKEN_ENV: self._token,
        }

    def http_auth_header(self) -> Optional[str]:
        """Return a Basic Authorization header for process-local Windows Git."""
        if sys.platform != "win32" or not self._token:
            return None
        payload = f"{self._username}:{self._token}".encode("utf-8")
        encoded = base64.b64encode(payload).decode("ascii")
        return f"Authorization: Basic {encoded}"

    def _create_askpass_script(self) -> Path:
        """Create the non-Windows secret-free helper used by Git."""
        content = '''#!/bin/sh
case "$1" in
  *Username*|*username*) printf '%s\\n' "$CENTERMANAGER_GIT_USERNAME" ;;
  *) printf '%s\\n' "$CENTERMANAGER_GIT_TOKEN" ;;
esac
'''
        fd, path = tempfile.mkstemp(suffix=".sh", prefix="git-askpass-", text=True)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(content)
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
