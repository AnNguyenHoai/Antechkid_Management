# -*- coding: utf-8 -*-
"""Runtime Git origin reconciliation.

This module keeps the repository-origin safety fix isolated from the large
GitSynchronizationProvider implementation.  The provider class is patched at
package initialization so every import path uses the same reconciliation
behavior.
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def _normalize_remote_url(url: str) -> str:
    """Normalize Git remote URLs for comparison without changing credentials."""
    value = (url or "").strip()
    if value.endswith("/"):
        value = value[:-1]
    if value.endswith(".git"):
        value = value[:-4]
    return value.lower()


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
