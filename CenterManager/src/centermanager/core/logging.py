# -*- coding: utf-8 -*-
"""
Logging setup for CenterManager.

Configures console and file logging with UTF-8 encoding and redacts
credential-bearing Git URLs and common token formats from rendered logs.
"""
import logging
import re
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler


_SENSITIVE_PATTERNS = (
    (re.compile(r"(?i)(https?://)([^\s/@:]+(?::[^\s/@]*)?@)"), r"\1[REDACTED]@"),
    (re.compile(r"(?i)\b(?:ghp|gho|ghu|ghs|ghr|github_pat)_[A-Za-z0-9_\-]+\b"), "[REDACTED_TOKEN]"),
    (re.compile(r"(?i)(\b(?:token|access_token|password|passwd|secret)\s*[=:]\s*)[^\s,&]+"), r"\1[REDACTED]"),
)


def redact_sensitive_text(text: str) -> str:
    """Redact credential material before it reaches console or file logs."""
    redacted = text
    for pattern, replacement in _SENSITIVE_PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted


class RedactingFormatter(logging.Formatter):
    """Formatter that sanitizes the fully rendered record, including tracebacks."""

    def format(self, record: logging.LogRecord) -> str:
        return redact_sensitive_text(super().format(record))


def setup_logging(
    log_dir: Path,
    app_name: str = "CenterManager",
    app_version: str = "0.1.0",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 3,
) -> None:
    """Configure console and file logging with credential redaction."""
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{app_name.lower().replace(' ', '_')}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper(), logging.INFO))
    console_handler.setFormatter(
        RedactingFormatter(
            "%(levelname)s - %(name)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
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
        RedactingFormatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root_logger.addHandler(file_handler)

    logger = logging.getLogger("centermanager")
    logger.info(f"{app_name} v{app_version} starting")
    logger.info(f"Log file: {log_file}")
