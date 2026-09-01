# -*- coding: utf-8 -*-
"""Runtime Git origin reconciliation.

This module keeps the repository-origin safety fix isolated from the large
GitSynchronizationProvider implementation. The provider class is patched at
package initialization so every import path uses the same reconciliation
behavior.
"""

import logging
import os
import re
from typing import Any
from urllib.parse import unquote, urlsplit

logger = logging.getLogger(__name__)


_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _normalize_local_path(value: str) -> str:
    """Canonicalize a local filesystem path for cross-platform comparison."""
    value = unquote(value.strip())
    value = value.replace("\\", "/")

    if re.match(r"^/[A-Za-z]:/", value):
        value = value[1:]

    value = os.path.normpath(value).replace("\\", "/")
    value = value.rstrip("/")

    if value.lower().endswith(".git"):
        value = value[:-4]

    return value.lower()


def _normalize_remote_url(url: str) -> str:
    """Normalize Git remotes while preserving URL semantics and credentials.

    Local filesystem remotes need filesystem-aware normalization because Git
    can return a Windows path using a different slash style from the path that
    was supplied to the provider. Network URLs are normalized independently so
    their scheme/host/path semantics are not changed by filesystem handling.
    """
    value = (url or "").strip()
    if not value:
        return ""

    parsed = urlsplit(value)
    if parsed.scheme.lower() == "file":
        if parsed.netloc.lower() not in ("", "localhost"):
            path = f"//{parsed.netloc}{parsed.path}"
        else:
            path = parsed.path
        return _normalize_local_path(path)

    if parsed.scheme:
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc.lower()
        path = parsed.path.rstrip("/")
        if path.lower().endswith(".git"):
            path = path[:-4]
        return f"{scheme}://{netloc}{path}" + (f"?{parsed.query}" if parsed.query else "")

    if ":" in value and not _WINDOWS_DRIVE_RE.match(value):
        head, tail = value.split(":", 1)
        tail = tail.rstrip("/")
        if tail.lower().endswith(".git"):
            tail = tail[:-4]
        return f"{head.lower()}:{tail.lower()}"

    return _normalize_local_path(value)


def _get_origin_url(provider: Any) -> str:
    """Return the runtime repository's origin URL, or an empty string."""
    repo = getattr(provider, "_repo", None)
    if repo is None:
        return ""
    try:
        return repo.remote("origin").url or ""
    except ValueError:
        return ""
    except Exception:
        logger.exception("Failed to read runtime Git origin URL")
        return ""


def _reconcile_origin(provider: Any) -> bool:
    """Make an existing runtime clone follow the configured repository URL."""
    configured = (getattr(provider, "_repository_url", "") or "").strip()
    repo = getattr(provider, "_repo", None)

    if repo is None or not configured:
        return True

    current = _get_origin_url(provider)
    if _normalize_remote_url(current) == _normalize_remote_url(configured):
        logger.info("Runtime repository origin verified: %s", current or configured)
        return True

    try:
        if current:
            logger.warning(
                "Runtime repository origin mismatch; replacing remote. current=%s configured=%s",
                current,
                configured,
            )
            repo.remote("origin").set_url(configured)
        else:
            repo.create_remote("origin", configured)

        verified = _get_origin_url(provider)
        if _normalize_remote_url(verified) != _normalize_remote_url(configured):
            logger.error(
                "Failed to reconcile runtime repository origin: current=%s configured=%s",
                verified,
                configured,
            )
            return False

        logger.info(
            "Runtime repository origin reconciled to configured repository: %s",
            verified,
        )
        return True
    except Exception:
        logger.exception("Failed to reconcile runtime repository origin")
        return False


def install_origin_reconciliation(provider_cls: Any) -> None:
    """Install origin reconciliation around the provider's existing connect()."""
    if getattr(provider_cls, "_origin_reconciliation_installed", False):
        return

    original_connect = provider_cls.connect

    def connect_with_reconciled_origin(self):
        result = original_connect(self)
        if not result:
            return False

        if not _reconcile_origin(self):
            self._offline = True
            return False

        return True

    provider_cls.connect = connect_with_reconciled_origin
    provider_cls._origin_reconciliation_installed = True
