import base64

from centermanager.platform.synchronization.git.git_credential_helper import (
    GitCredentialHelper,
)
from centermanager.platform.synchronization.git_synchronization_provider import (
    GitSynchronizationProvider,
)
import centermanager.platform.synchronization.git.git_credential_helper as helper_module


def test_windows_credentials_do_not_create_askpass_process(monkeypatch):
    monkeypatch.setattr(helper_module.sys, "platform", "win32")
    helper = GitCredentialHelper("alice", "secret-token")

    env = helper.setup_environment()

    assert env["GIT_TERMINAL_PROMPT"] == "0"
    assert "GIT_ASKPASS" not in env
    assert "CENTERMANAGER_GIT_USERNAME" not in env
    assert "CENTERMANAGER_GIT_TOKEN" not in env
    assert helper._askpass_path is None

    encoded = base64.b64encode(b"alice:secret-token").decode("ascii")
    assert helper.http_auth_header() == f"Authorization: Basic {encoded}"


def test_provider_uses_per_process_http_auth_config_on_windows(monkeypatch):
    monkeypatch.setattr(helper_module.sys, "platform", "win32")
    helper = GitCredentialHelper("alice", "secret-token")

    provider = object.__new__(GitSynchronizationProvider)
    provider._repository_url = "https://github.com/example/repository.git"
    provider._credential_helper = helper
    provider._askpass_env = helper.setup_environment()

    env = GitSynchronizationProvider._get_env(provider)

    assert env["GIT_CONFIG_COUNT"] == "3"
    assert env["GIT_CONFIG_KEY_0"] == "credential.helper"
    assert env["GIT_CONFIG_KEY_1"] == "core.askpass"
    assert env["GIT_CONFIG_KEY_2"] == "http.extraHeader"
    assert env["GIT_CONFIG_VALUE_2"].startswith("Authorization: Basic ")
    assert "GIT_ASKPASS" not in env
    assert "secret-token" not in " ".join(
        value for key, value in env.items() if key.startswith("GIT_CONFIG_KEY_")
    )


def test_non_http_repository_does_not_receive_authorization_header(monkeypatch):
    monkeypatch.setattr(helper_module.sys, "platform", "win32")
    helper = GitCredentialHelper("alice", "secret-token")

    provider = object.__new__(GitSynchronizationProvider)
    provider._repository_url = "git@github.com:example/repository.git"
    provider._credential_helper = helper
    provider._askpass_env = helper.setup_environment()

    env = GitSynchronizationProvider._get_env(provider)

    assert env["GIT_CONFIG_COUNT"] == "2"
    assert "http.extraHeader" not in {
        value for key, value in env.items() if key.startswith("GIT_CONFIG_KEY_")
    }
