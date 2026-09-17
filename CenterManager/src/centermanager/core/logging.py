# -*- coding: utf-8 -*-
"""Logging setup for CenterManager with release-safe redaction."""

import logging
import re
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


_SENSITIVE_PATTERNS = (
    # Credential-bearing or ordinary HTTP(S) Git remotes.
    (re.compile(r"(?i)https?://[^\s]+"), "[REDACTED_URL]"),
    # SCP-style Git remotes such as git@host:owner/repo.git.
    (re.compile(r"(?i)\b(?:git|ssh)@[^\s]+"), "[REDACTED_GIT_REMOTE]"),
    # Common GitHub/GitLab access-token formats.
    (re.compile(r"(?i)\b(?:ghp|gho|ghu|ghs|ghr|github_pat|glpat)-?[A-Za-z0-9_\-]+\b"), "[REDACTED_TOKEN]"),
    # Generic credential key/value material.
    (re.compile(r"(?i)(\b(?:token|access_token|password|passwd|secret|api[_-]?key)\s*[=:]\s*)[^\s,&]+"), r"\1[REDACTED]"),
    # Windows drive / UNC paths and common POSIX absolute paths.
    (re.compile(r"(?i)(?:[A-Z]:[\\/]|\\\\)[^\s\"']+"), "[REDACTED_PATH]"),
    (re.compile(r"(?<![A-Za-z0-9_])/(?:Users|home|tmp|var|opt|mnt|workspace|workspaces)/[^\s\"']+"), "[REDACTED_PATH]"),
)


def redact_sensitive_text(text: str) -> str:
    """Remove credentials, Git remotes, and local filesystem paths from logs."""
    redacted = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class RedactingFormatter(logging.Formatter):
    """Sanitize the complete rendered record, including exception tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive_text(super().format(record))


def setup_logging(
    log_dir: Path,
    app_name: str = "CenterManager",
    app_version: str = "0.1.0",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    max_bytes: int = 5 * 1024 * 1024,
    backup_count: int = 3,
) -> None:
    """Configure console and file logging with release-safe redaction."""
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{app_name.lower().replace(' ', '_')}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper(), logging.INFO))
    console_handler.setFormatter(
        RedactingFormatter("%(levelname)s - %(name)s - %(message)s")
    )
    root_logger.addHandler(console_handler)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, file_level.upper(), logging.DEBUG))
    file_handler.setFormatter(
        RedactingFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )
    root_logger.addHandler(file_handler)

    logger = logging.getLogger("centermanager")
    logger.info(f"{app_name} v{app_version} starting")
    # Deliberately do not log the concrete filesystem path of the log file.
    logger.info("File logging initialized")
