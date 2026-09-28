from types import SimpleNamespace

import pytest

from centermanager.platform.synchronization.exceptions import (
    AuthenticationFailedError,
)
from centermanager.platform.synchronization.git_provider_safety import (
    install_git_command_serialization,
)


class _Provider:
    def __init__(self, repo_path, git_executable="git"):
        self._repo_path = repo_path
        self._git_executable = git_executable
        self._offline = False

    def _get_env(self):
        return {"TEST_ENV": "1"}

    def _run_git_command(self, args, cwd=None, check=True, env=None):
        raise AssertionError("installer must replace locale-dependent runner")


def _installed_provider(tmp_path):
    class Provider(_Provider):
        pass

    install_git_command_serialization(Provider)
    return Provider(tmp_path)


def test_git_output_is_captured_as_bytes_and_invalid_utf8_is_replaced(monkeypatch, tmp_path):
    provider = _installed_provider(tmp_path)
    observed = {}

    def fake_run(*args, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=b"ok-\x81-result\n", stderr=b"")

    monkeypatch.setattr(
        "centermanager.platform.synchronization.git_provider_safety.subprocess.run",
        fake_run,
    )

    output = provider._run_git_command(["status"])

    assert observed["text"] is False
    assert output == "ok-\ufffd-result"


def test_none_stderr_never_causes_secondary_attribute_error(monkeypatch, tmp_path):
    provider = _installed_provider(tmp_path)

    monkeypatch.setattr(
        "centermanager.platform.synchronization.git_provider_safety.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=128, stdout=b"", stderr=None),
    )

    with pytest.raises(RuntimeError, match="exit code 128"):
        provider._run_git_command(["clone", "origin"])


def test_authentication_classification_survives_undecodable_bytes(monkeypatch, tmp_path):
    provider = _installed_provider(tmp_path)

    monkeypatch.setattr(
        "centermanager.platform.synchronization.git_provider_safety.subprocess.run",
        lambda *a, **k: SimpleNamespace(
            returncode=128,
            stdout=b"",
            stderr=b"fatal: authentication failed \x81 403",
        ),
    )

    with pytest.raises(AuthenticationFailedError, match="authentication failed"):
        provider._run_git_command(["clone", "origin"])


def test_nonfatal_failure_returns_empty_string(monkeypatch, tmp_path):
    provider = _installed_provider(tmp_path)

    monkeypatch.setattr(
        "centermanager.platform.synchronization.git_provider_safety.subprocess.run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout=b"", stderr=b"bad \x81 output"),
    )

    assert provider._run_git_command(["show", "missing"], check=False) == ""
