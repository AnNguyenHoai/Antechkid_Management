"""Locale-independent, windowless subprocess boundary for the active Git provider."""

import logging
import os
import subprocess
from typing import Any

from .exceptions import (
    AuthenticationFailedError,
    GitNotInstalledError,
    RemoteUnavailableError,
    RepositoryConflictError,
)

logger = logging.getLogger(__name__)


def _decode(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def _windows_hidden_process_kwargs() -> dict:
    """Prevent child console windows from flashing for packaged GUI builds."""
    if os.name != "nt":
        return {}

    kwargs = {}
    create_no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    if create_no_window:
        kwargs["creationflags"] = create_no_window

    startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
    startf_use_showwindow = getattr(subprocess, "STARTF_USESHOWWINDOW", 0)
    sw_hide = getattr(subprocess, "SW_HIDE", 0)
    if startupinfo_cls is not None and startf_use_showwindow:
        startupinfo = startupinfo_cls()
        startupinfo.dwFlags |= startf_use_showwindow
        startupinfo.wShowWindow = sw_hide
        kwargs["startupinfo"] = startupinfo
    return kwargs


def install_git_output_safety(provider_cls: Any) -> None:
    """Install byte-safe, windowless Git runner before credential/log wrappers.

    Windows text-mode subprocess decoding uses the host locale and can fail in
    reader threads before the provider receives stderr. Capturing bytes avoids
    that failure; UTF-8 replacement decoding keeps diagnostics available while
    later credential-safety wrappers still sanitize argv and surfaced errors.

    Packaged CenterManager is a GUI application, so Git is infrastructure and
    must not create transient console windows during clone/fetch/pull/push.
    """
    if getattr(provider_cls, "_git_output_safety_installed", False):
        return

    def safe_run_git_command(self, args, cwd=None, check=True, env=None):
        if cwd is None:
            cwd = self._repo_path
        if env is None:
            env = self._get_env()

        logger.debug("Running git: %s", " ".join(str(arg) for arg in args))
        if not self._git_executable:
            self._offline = True
            raise GitNotInstalledError(
                "Git executable not found. Configure portable Git or install Git."
            )

        result = subprocess.run(
            [self._git_executable] + list(args),
            cwd=str(cwd),
            capture_output=True,
            text=False,
            env=env,
            check=False,
            **_windows_hidden_process_kwargs(),
        )
        stdout = _decode(result.stdout)
        stderr = _decode(result.stderr)

        if result.returncode != 0:
            stderr_lower = stderr.lower()
            detail = stderr.strip() or stdout.strip() or f"exit code {result.returncode}"
            if check:
                if "authentication" in stderr_lower or "401" in stderr_lower or "403" in stderr_lower:
                    raise AuthenticationFailedError(
                        f"Git authentication failed: {detail}"
                    )
                if "could not read from remote" in stderr_lower or "remote error" in stderr_lower:
                    raise RemoteUnavailableError(f"Remote unavailable: {detail}")
                if "diverg" in stderr_lower or "non-fast-forward" in stderr_lower or "rejected" in stderr_lower:
                    raise RepositoryConflictError(f"Conflict: {detail}")
                raise RuntimeError(f"Git command failed: {detail}")
            logger.debug("Git command failed (non-fatal): %s", detail)
            return ""

        return stdout.strip()

    provider_cls._run_git_command = safe_run_git_command
    provider_cls._git_output_safety_installed = True
