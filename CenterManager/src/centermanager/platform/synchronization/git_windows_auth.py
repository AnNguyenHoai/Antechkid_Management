"""Process-free Windows HTTPS authentication for the Git provider."""

from __future__ import annotations

from typing import Any


def install_windows_http_auth(provider_cls: Any) -> None:
    """Inject HTTPS credentials through process-local Git configuration.

    ``GIT_ASKPASS`` is intentionally avoided on Windows GUI builds because a
    batch askpass helper is executed through ``cmd.exe`` and can flash a console
    window.  ``GIT_CONFIG_*`` is inherited by the already-windowless git.exe
    process, keeping the credential out of argv while avoiding helper children.
    """
    if getattr(provider_cls, "_windows_http_auth_installed", False):
        return

    original_get_env = provider_cls._get_env

    def get_env_with_windows_http_auth(self) -> dict:
        env = original_get_env(self)
        helper = getattr(self, "_credential_helper", None)
        repository_url = str(getattr(self, "_repository_url", "") or "")
        if helper is None or not repository_url.lower().startswith(("http://", "https://")):
            return env

        auth_header = helper.http_auth_header()
        if not auth_header:
            return env

        try:
            config_count = int(env.get("GIT_CONFIG_COUNT", "0"))
        except (TypeError, ValueError):
            config_count = 0

        env[f"GIT_CONFIG_KEY_{config_count}"] = "http.extraHeader"
        env[f"GIT_CONFIG_VALUE_{config_count}"] = auth_header
        env["GIT_CONFIG_COUNT"] = str(config_count + 1)
        return env

    provider_cls._get_env = get_env_with_windows_http_auth
    provider_cls._windows_http_auth_installed = True
