# -*- coding: utf-8 -*-
"""Credential and transport safety boundary for the active Git provider."""

import logging
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from centermanager.core.git_url_safety import validate_repository_url


_URL_USERINFO_RE = re.compile(r"(?P<scheme>[A-Za-z][A-Za-z0-9+.-]*://)[^/@\s]+@")


def _strip_url_credentials(value: str) -> str:
    """Return a URL without embedded userinfo; leave non-URLs unchanged."""
    text = str(value)
    if "://" not in text or "@" not in text:
        return text

    try:
        parsed = urlsplit(text)
    except ValueError:
        return text

    if not parsed.scheme or not parsed.netloc or "@" not in parsed.netloc:
        return text

    host = parsed.netloc.rsplit("@", 1)[-1]
    return urlunsplit((parsed.scheme, host, parsed.path, parsed.query, parsed.fragment))


def _redact_text(value: str, secrets: set[str] | None = None) -> str:
    """Redact URL userinfo and registered secrets from arbitrary text."""
    text = str(value)
    for secret in secrets or set():
        if secret:
            text = text.replace(secret, "***")
    return _URL_USERINFO_RE.sub(lambda match: f"{match.group('scheme')}***@", text)


class _GitCredentialRedactionFilter(logging.Filter):
    """Redact provider credentials before a log record leaves the module."""

    def __init__(self) -> None:
        super().__init__()
        self._secrets: set[str] = set()

    def register(self, secret: str) -> None:
        if secret:
            self._secrets.add(str(secret))

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            rendered = record.getMessage()
            record.msg = _redact_text(rendered, self._secrets)
            record.args = ()
        except Exception:
            # Logging safety must never break Git execution.
            pass
        return True


def install_git_credential_safety(provider_cls: Any) -> None:
    """Keep credentials out of argv/logs and enforce the Git transport policy.

    Normal application repositories are credential-free HTTPS URLs. Isolated
    SEC06/manual fixtures may explicitly opt into a local ``file://`` remote by
    passing ``allow_local_file_remote=True`` when the provider is constructed.
    """
    if getattr(provider_cls, "_git_credential_safety_installed", False):
        return

    original_init = provider_cls.__init__
    original_run_git_command = provider_cls._run_git_command
    provider_logger = logging.getLogger(provider_cls.__module__)
    redaction_filter = _GitCredentialRedactionFilter()
    provider_logger.addFilter(redaction_filter)

    def credential_safe_init(self, *args, **kwargs):
        allow_local_file_remote = bool(kwargs.pop("allow_local_file_remote", False))

        # repository_url is the second positional argument in the current
        # provider signature. Prefer the keyword form used by production.
        if "repository_url" in kwargs:
            raw_url = kwargs.get("repository_url", "")
            if raw_url:
                kwargs["repository_url"] = validate_repository_url(
                    raw_url,
                    allow_local_file_remote=allow_local_file_remote,
                )
        elif len(args) >= 2 and args[1]:
            args = list(args)
            args[1] = validate_repository_url(
                args[1],
                allow_local_file_remote=allow_local_file_remote,
            )
            args = tuple(args)

        original_init(self, *args, **kwargs)
        self._allow_local_file_remote = allow_local_file_remote

    def repository_url_without_credentials(self) -> str:
        return _strip_url_credentials(getattr(self, "_repository_url", ""))

    def credential_safe_run_git_command(self, args, *run_args, **run_kwargs):
        token = str(getattr(self, "_token", "") or "")
        redaction_filter.register(token)
        safe_args = [_strip_url_credentials(str(arg)) for arg in args]
        try:
            return original_run_git_command(self, safe_args, *run_args, **run_kwargs)
        except Exception as exc:
            safe_message = _redact_text(str(exc), {token} if token else set())
            if safe_message != str(exc):
                exc.args = (safe_message,) + tuple(exc.args[1:])
            raise

    # The legacy clone implementation asks this method for an authenticated URL.
    # Keep it for compatibility, but it can only return a credential-free URL.
    provider_cls.__init__ = credential_safe_init
    provider_cls._build_authenticated_url = repository_url_without_credentials
    provider_cls._run_git_command = credential_safe_run_git_command
    provider_cls._git_credential_redaction_filter = redaction_filter
    provider_cls._git_credential_safety_installed = True
