"""Process-free Windows HTTPS authentication for Git subprocesses."""

from __future__ import annotations

from typing import Any, MutableMapping, Optional


def append_http_auth_config(
    env: MutableMapping[str, str],
    repository_url: str,
    auth_header: Optional[str],
) -> MutableMapping[str, str]:
    """Append an HTTPS Authorization header to process-local Git config.

    The secret remains outside Git argv and no credential-helper child process is
    needed. Existing ``GIT_CONFIG_*`` entries are preserved, so callers may
    first install hardening entries such as ``credential.helper=`` and
    ``core.askpass=`` and then add authentication with this helper.
    """
    if not auth_header or not str(repository_url or "").lower().startswith(("http://", "https://")):
        return env

    try:
        config_count = int(env.get("GIT_CONFIG_COUNT", "0"))
    except (TypeError, ValueError):
        config_count = 0

    env[f"GIT_CONFIG_KEY_{config_count}"] = "http.extraHeader"
    env[f"GIT_CONFIG_VALUE_{config_count}"] = auth_header
    env["GIT_CONFIG_COUNT"] = str(config_count + 1)
    return env


def install_windows_http_auth(provider_cls: Any) -> None:
    """Inject HTTPS credentials through process-local Git configuration.

    ``GIT_ASKPASS`` is intentionally avoided on Windows GUI builds because a
    batch askpass helper is executed through ``cmd.exe`` and can flash a console
    window. ``GIT_CONFIG_*`` is inherited by the already-windowless git.exe
    process, keeping the credential out of argv while avoiding helper children.
    """
    if getattr(provider_cls, "_windows_http_auth_installed", False):
        return

    original_get_env = provider_cls._get_env

    def get_env_with_windows_http_auth(self) -> dict:
        env = original_get_env(self)
        helper = getattr(self, "_credential_helper", None)
        repository_url = str(getattr(self, "_repository_url", "") or "")
        if helper is None:
            return env

        return dict(append_http_auth_config(env, repository_url, helper.http_auth_header()))

    provider_cls._get_env = get_env_with_windows_http_auth
    provider_cls._windows_http_auth_installed = True
