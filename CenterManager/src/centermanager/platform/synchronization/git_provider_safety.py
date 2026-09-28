"""Thread-safety and Windows-safe subprocess boundary for Git providers."""

import subprocess
import threading
from pathlib import Path
from typing import Any

from .exceptions import (
    AuthenticationFailedError,
    GitNotInstalledError,
    RemoteUnavailableError,
    RepositoryConflictError,
)


def _decode_git_output(value) -> str:
    """Decode Git output deterministically without depending on Windows ACP."""
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def install_git_command_serialization(provider_cls: Any) -> None:
    """Install the process-wide Git subprocess safety boundary.

    Git commands are serialized per provider and their output is captured as
    bytes.  Decoding subprocess pipes with ``text=True`` uses the host Windows
    code page; portable Git can emit byte sequences that are invalid in that
    code page, killing Python's reader thread and leaving stderr as ``None``.
    Capturing bytes and decoding with replacement keeps the real Git failure
    observable and prevents a secondary ``None.lower()`` crash.
    """
    if getattr(provider_cls, "_git_command_serialization_installed", False):
        return

    original_init = provider_cls.__init__

    def init_with_command_lock(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._git_command_lock = threading.RLock()

    def serialized_run_git_command(self, args, cwd=None, check=True, env=None):
        lock = getattr(self, "_git_command_lock", None)
        if lock is None:
            lock = threading.RLock()
            self._git_command_lock = lock

        if cwd is None:
            cwd = self._repo_path
        if env is None:
            env = self._get_env()

        git_executable = getattr(self, "_git_executable", "")
        if not git_executable:
            self._offline = True
            raise GitNotInstalledError(
                "Git executable not found. Configure portable Git or install Git."
            )

        with lock:
            result = subprocess.run(
                [git_executable] + list(args),
                cwd=str(Path(cwd)),
                capture_output=True,
                text=False,
                env=env,
                check=False,
            )

        stdout = _decode_git_output(result.stdout)
        stderr = _decode_git_output(result.stderr)
        if result.returncode != 0:
            detail = stderr.strip() or stdout.strip() or f"exit code {result.returncode}"
            lowered = detail.lower()
            if check:
                if "authentication" in lowered or "401" in lowered or "403" in lowered:
                    raise AuthenticationFailedError(
                        f"Git authentication failed: {detail}"
                    )
                if "could not read from remote" in lowered or "remote error" in lowered:
                    raise RemoteUnavailableError(f"Remote unavailable: {detail}")
                if "diverg" in lowered or "non-fast-forward" in lowered or "rejected" in lowered:
                    raise RepositoryConflictError(f"Conflict: {detail}")
                raise RuntimeError(f"Git command failed: {detail}")
            return ""

        return stdout.strip()

    provider_cls.__init__ = init_with_command_lock
    provider_cls._run_git_command = serialized_run_git_command
    provider_cls._git_command_serialization_installed = True
