# -*- coding: utf-8 -*-
"""Credential-safety boundary for the active Git synchronization provider.

Git credentials belong in the non-interactive askpass environment, never in
Git command arguments. This installer keeps the provider's existing behavior
while stripping any accidentally embedded URL credentials before subprocess
execution.
"""

from typing import Any
from urllib.parse import urlsplit, urlunsplit


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


def install_git_credential_safety(provider_cls: Any) -> None:
    """Keep credentials out of argv for every subprocess Git operation.

    The provider already owns a ``GitCredentialHelper`` which supplies the
    username/token through ``GIT_ASKPASS`` environment variables. Therefore
    embedding the token into an HTTPS URL is both unnecessary and unsafe.
    """
    if getattr(provider_cls, "_git_credential_safety_installed", False):
        return

    original_run_git_command = provider_cls._run_git_command

    def repository_url_without_credentials(self) -> str:
        return _strip_url_credentials(getattr(self, "_repository_url", ""))

    def credential_safe_run_git_command(self, args, *run_args, **run_kwargs):
        safe_args = [_strip_url_credentials(str(arg)) for arg in args]
        return original_run_git_command(self, safe_args, *run_args, **run_kwargs)

    # clone() in the legacy implementation asks this helper for an auth URL.
    # Keep the method for compatibility, but it now always returns a clean URL.
    provider_cls._build_authenticated_url = repository_url_without_credentials
    provider_cls._run_git_command = credential_safe_run_git_command
    provider_cls._git_credential_safety_installed = True
