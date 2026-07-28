# -*- coding: utf-8 -*-
"""
Logging setup for CenterManager.

Configures console and file logging with UTF-8 encoding.
"""
import logging
import sys
from pathlib import Path
from logging.handlers import RotatingFileHandler
from typing import Optional


def setup_logging(
    log_dir: Path,
    app_name: str = "CenterManager",
    app_version: str = "0.1.0",
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    max_bytes: int = 5 * 1024 * 1024,  # 5MB
    backup_count: int = 3,
) -> None:
    """
    Configure logging for both console and file.

    Args:
        log_dir: Directory to store log files.
        app_name: Application name for log header.
        app_version: Application version for log header.
        console_level: Log level for console output.
        file_level: Log level for file output.
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of rotated log files to keep.
    """
    # Ensure log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)

    log_file = log_dir / f"{app_name.lower().replace(' ', '_')}.log"

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # Allow all levels, handlers filter

    # Remove any existing handlers to avoid duplicates
    root_logger.handlers.clear()

    # ----- Console handler -----
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper(), logging.INFO))
    console_format = logging.Formatter(
        "%(levelname)s - %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # ----- File handler (with rotation) -----
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    file_handler.setLevel(getattr(logging, file_level.upper(), logging.DEBUG))
    file_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_format)
    root_logger.addHandler(file_handler)

    # Log startup banner
    logger = logging.getLogger("centermanager")
    logger.info(f"{app_name} v{app_version} starting")
    logger.info(f"Log file: {log_file}")