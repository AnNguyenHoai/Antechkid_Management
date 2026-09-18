# -*- coding: utf-8 -*-
"""Credential-safe Git URL helpers."""

from urllib.parse import urlsplit, urlunsplit


def sanitize_repository_url(url: str) -> str:
    """Remove HTTP(S) user-info so credentials are never persisted in Git config.

    SSH/SCP-style URLs are left unchanged because their username is routing
    information rather than an HTTP credential. Authentication is supplied by
    the existing askpass boundary instead of URL user-info.
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
