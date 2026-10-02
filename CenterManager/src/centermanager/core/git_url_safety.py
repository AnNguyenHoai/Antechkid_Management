# -*- coding: utf-8 -*-
"""Credential-safe Git URL validation and normalization."""

from urllib.parse import urlsplit, urlunsplit


class RepositoryUrlPolicyError(ValueError):
    """Raised when a repository URL violates the CenterManager transport policy."""


def sanitize_repository_url(url: str) -> str:
    """Remove HTTP(S) user-info so credentials are never persisted in Git config.

    This helper remains for redaction/legacy cleanup. Security-sensitive callers
    must use :func:`validate_repository_url`, which rejects embedded credentials
    instead of silently accepting them.
    """
    value = (url or "").strip()
    parsed = urlsplit(value)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        return value

    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def validate_repository_url(url: str, *, allow_local_file_remote: bool = False) -> str:
    """Validate and return a credential-free repository URL.

    Production repository transport is HTTPS-only. A ``file://`` remote is
    accepted only when the caller explicitly opts in; this exists solely for
    isolated SEC06/manual test fixtures and is persisted inside the encrypted
    Git configuration. HTTP, SSH/SCP-style URLs, and URLs containing user-info
    are rejected fail-closed.
    """
    value = (url or "").strip()
    if not value:
        raise RepositoryUrlPolicyError("Repository URL is required")

    try:
        parsed = urlsplit(value)
    except ValueError as exc:
        raise RepositoryUrlPolicyError("Repository URL is invalid") from exc

    scheme = parsed.scheme.lower()
    if scheme == "file":
        if not allow_local_file_remote:
            raise RepositoryUrlPolicyError("Local file repository URLs are disabled")
        if parsed.username is not None or parsed.password is not None:
            raise RepositoryUrlPolicyError("Repository URL must not contain credentials")
        if not parsed.path:
            raise RepositoryUrlPolicyError("Local file repository URL must contain a path")
        return value

    if scheme != "https":
        raise RepositoryUrlPolicyError("Repository URL must use HTTPS")
    if not parsed.hostname:
        raise RepositoryUrlPolicyError("Repository URL must contain a host")
    if parsed.username is not None or parsed.password is not None:
        raise RepositoryUrlPolicyError("Repository URL must not contain credentials")

    # Rebuild the netloc from parsed host/port so persisted values can never
    # retain user-info even if urllib parsing behavior changes at a call site.
    host = parsed.hostname
    if ":" in host and not host.startswith("["):
        host = f"[{host}]"
    if parsed.port is not None:
        host = f"{host}:{parsed.port}"
    return urlunsplit(("https", host, parsed.path, parsed.query, parsed.fragment))
