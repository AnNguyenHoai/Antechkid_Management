# -*- coding: utf-8 -*-
"""Runtime Git origin reconciliation without sensitive logging."""

import logging
import ntpath
import posixpath
import re
from typing import Any
from urllib.parse import unquote, urlsplit

logger = logging.getLogger(__name__)

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")


def _normalize_local_path(value: str) -> str:
    """Return one platform-independent canonical form for a local Git path."""
    value = unquote((value or "").strip()).replace("\\", "/")
    if re.match(r"^/[A-Za-z]:/", value):
        value = value[1:]

    if re.match(r"^[A-Za-z]:/", value):
        value = ntpath.normpath(value).replace("\\", "/")
    elif value.startswith("//"):
        value = ntpath.normpath(value).replace("\\", "/")
    else:
        value = posixpath.normpath(value)

    if value == ".":
        value = ""
    value = value.rstrip("/")
    if value.lower().endswith(".git"):
        value = value[:-4].rstrip("/")
    return value.lower()


def _normalize_remote_url(url: str) -> str:
    """Canonicalize local and network Git origins without mixing their semantics."""
    value = (url or "").strip()
    if not value:
        return ""

    if _WINDOWS_DRIVE_RE.match(value):
        return _normalize_local_path(value)

    parsed = urlsplit(value)

    if parsed.scheme.lower() == "file":
        path = parsed.path
        if parsed.netloc and parsed.netloc.lower() != "localhost":
            path = f"//{parsed.netloc}{path}"
        return _normalize_local_path(path)

    if not parsed.scheme and ":" in value:
        head, tail = value.split(":", 1)
        if not re.match(r"^[A-Za-z]$", head):
            tail = tail.rstrip("/")
            if tail.lower().endswith(".git"):
                tail = tail[:-4]
            return f"{head.lower()}:{tail.lower()}"

    if parsed.scheme:
        scheme = parsed.scheme.lower()
        netloc = parsed.netloc
        if parsed.hostname:
            host = parsed.hostname.lower()
            if ":" in host and not host.startswith("["):
                host = f"[{host}]"
            if parsed.port is not None:
                host = f"{host}:{parsed.port}"
            if parsed.username is not None:
                user = unquote(parsed.username)
                password = parsed.password
                auth = user
                if password is not None:
                    auth += f":{unquote(password)}"
                netloc = f"{auth}@{host}"
            else:
                netloc = host
        else:
            netloc = netloc.lower()

        path = unquote(parsed.path).replace("\\", "/").rstrip("/")
        if path.lower().endswith(".git"):
            path = path[:-4]
        path = path.lower()

        result = f"{scheme}://{netloc}{path}"
        if parsed.query:
            result += f"?{parsed.query}"
        if parsed.fragment:
            result += f"#{parsed.fragment}"
        return result

    return _normalize_local_path(value)


def _get_origin_url(provider: Any) -> str:
    """Return the runtime repository origin URL, or an empty string."""
    repo = getattr(provider, "_repo", None)
    if repo is None:
        return ""
    try:
        return repo.remote("origin").url or ""
    except ValueError:
        return ""
    except Exception:
        logger.error("Failed to read runtime Git origin URL")
        return ""


def _reconcile_origin(provider: Any) -> bool:
    """Ensure an existing runtime clone has the configured canonical origin."""
    configured = (getattr(provider, "_repository_url", "") or "").strip()
    repo = getattr(provider, "_repo", None)

    if repo is None or not configured:
        return True

    current = _get_origin_url(provider)
    if _normalize_remote_url(current) == _normalize_remote_url(configured):
        logger.info("Runtime repository origin verified")
        return True

    try:
        if current:
            logger.warning("Runtime repository origin mismatch; replacing remote")
            repo.remote("origin").set_url(configured)
        else:
            repo.create_remote("origin", configured)

        verified = _get_origin_url(provider)
        if _normalize_remote_url(verified) != _normalize_remote_url(configured):
            logger.error("Failed to reconcile runtime repository origin")
            return False

        logger.info("Runtime repository origin reconciled")
        return True
    except Exception:
        logger.error("Failed to reconcile runtime repository origin")
        return False


def install_origin_reconciliation(provider_cls: Any) -> None:
    """Install origin reconciliation around the provider's existing connect()."""
    if getattr(provider_cls, "_origin_reconciliation_installed", False):
        return

    original_connect = provider_cls.connect
    original_clone = provider_cls.clone

    def clone_idempotent(self, progress_callback=None):
        repo_path = getattr(self, "_repo_path", None)
        if (
            getattr(self, "_repo", None) is not None
            and repo_path is not None
            and (repo_path / ".git").exists()
        ):
            if not _reconcile_origin(self):
                logger.error("Existing repository origin could not be reconciled")
                return False
            logger.info("Repository already exists; clone is idempotent")
            if progress_callback:
                progress_callback("clone", "Repository already exists", 100)
            return True

        return original_clone(self, progress_callback=progress_callback)

    provider_cls.clone = clone_idempotent

    def connect_with_reconciled_origin(self):
        result = original_connect(self)
        if not result:
            return False

        if getattr(self, "_repo", None) is None and getattr(self, "_repository_url", ""):
            try:
                if not self.clone():
                    self._offline = True
                    return False
            except Exception:
                logger.error("Failed to materialize configured repository during connect")
                self._offline = True
                return False

        if not _reconcile_origin(self):
            self._offline = True
            return False

        return True

    provider_cls.connect = connect_with_reconciled_origin
    provider_cls._origin_reconciliation_installed = True
