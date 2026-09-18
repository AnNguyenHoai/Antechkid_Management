# -*- coding: utf-8 -*-
"""Credential-safety boundary for the active Git synchronization provider.

Git credentials belong in the non-interactive askpass environment, never in
Git command arguments, logs, or surfaced exception text. This installer keeps
the provider's existing behavior while enforcing that boundary around every
subprocess Git operation.
"""

import logging
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit


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
    """Keep credentials out of argv, logs, and surfaced Git errors.

    The provider already owns a ``GitCredentialHelper`` which supplies the
    username/token through ``GIT_ASKPASS`` environment variables. Therefore
    embedding the token into an HTTPS URL is both unnecessary and unsafe.
    """
    if getattr(provider_cls, "_git_credential_safety_installed", False):
        return

    original_run_git_command = provider_cls._run_git_command
    provider_logger = logging.getLogger(provider_cls.__module__)
    redaction_filter = _GitCredentialRedactionFilter()
    provider_logger.addFilter(redaction_filter)

    def repository_url_without_credentials(self) -> str:
        return _strip_url_credentials(getattr(self, "_repository_url", ""))

    def credential_safe_run_git_command(self, args, *run_args, **run_kwargs):
        token = str(getattr(self, "_token", "") or "")
        redaction_filter.register(token)
        safe_args = [_strip_url_credentials(str(arg)) for arg in args]
        try:
            return original_run_git_command(self, safe_args, *run_args, **run_kwargs)
        except Exception as exc:
            # The base provider includes Git stderr in several exception
            # messages. Sanitize it before the exception reaches callers/UI.
            safe_message = _redact_text(str(exc), {token} if token else set())
            if safe_message != str(exc):
                exc.args = (safe_message,) + tuple(exc.args[1:])
            raise

    # clone() in the legacy implementation asks this helper for an auth URL.
    # Keep the method for compatibility, but it now always returns a clean URL.
    provider_cls._build_authenticated_url = repository_url_without_credentials
    provider_cls._run_git_command = credential_safe_run_git_command
    provider_cls._git_credential_redaction_filter = redaction_filter
    provider_cls._git_credential_safety_installed = True
