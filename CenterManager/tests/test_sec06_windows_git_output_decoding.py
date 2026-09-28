from types import SimpleNamespace

import pytest

import centermanager.platform.synchronization.git_output_safety as output_module
from centermanager.platform.synchronization.exceptions import AuthenticationFailedError
from centermanager.platform.synchronization.git_credential_safety import (
    install_git_credential_safety,
)
from centermanager.platform.synchronization.git_output_safety import (
    install_git_output_safety,
)


class _Provider:
    def __init__(self, repo_path, token="", git_executable="git"):
        self._repo_path = repo_path
        self._git_executable = git_executable
        self._offline = False
        self._token = token
        self._repository_url = "https://github.com/example/repo.git"

    def _get_env(self):
        return {"TEST_ENV": "1"}

    def _run_git_command(self, args, cwd=None, check=True, env=None):
        raise AssertionError("installer must replace locale-dependent runner")


def _installed_provider(tmp_path, token=""):
    class Provider(_Provider):
        pass

    install_git_output_safety(Provider)
    install_git_credential_safety(Provider)
    return Provider(tmp_path, token=token)


def test_git_output_is_captured_as_bytes_and_invalid_utf8_is_replaced(monkeypatch, tmp_path):
    provider = _installed_provider(tmp_path)
    observed = {}

    def fake_run(*args, **kwargs):
        observed.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=b"ok-\x81-result\n", stderr=b"")

    monkeypatch.setattr(output_module.subprocess, "run", fake_run)
    output = provider._run_git_command(["status"])

    assert observed["text"] is False
    assert output == "ok-\ufffd-result"


def test_none_stderr_never_causes_secondary_attribute_error(monkeypatch, tmp_path):
    provider = _installed_provider(tmp_path)
    monkeypatch.setattr(
        output_module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=128, stdout=b"", stderr=None),
    )

    with pytest.raises(RuntimeError, match="exit code 128"):
        provider._run_git_command(["clone", "origin"])


def test_authentication_classification_survives_undecodable_bytes(monkeypatch, tmp_path):
    provider = _installed_provider(tmp_path)
    monkeypatch.setattr(
        output_module.subprocess,
        "run",
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
        output_module.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout=b"", stderr=b"bad \x81 output"),
    )

    assert provider._run_git_command(["show", "missing"], check=False) == ""


def test_output_safety_composes_with_credential_safety(monkeypatch, tmp_path):
    secret = "secret-token"
    provider = _installed_provider(tmp_path, token=secret)
    observed = {}

    def fake_run(cmd, **kwargs):
        observed["cmd"] = list(cmd)
        return SimpleNamespace(
            returncode=128,
            stdout=b"",
            stderr=f"fatal: authentication failed for https://{secret}@github.com/example/repo.git".encode(),
        )

    monkeypatch.setattr(output_module.subprocess, "run", fake_run)

    with pytest.raises(AuthenticationFailedError) as exc_info:
        provider._run_git_command(
            ["fetch", f"https://{secret}@github.com/example/repo.git"]
        )

    assert secret not in " ".join(observed["cmd"])
    assert secret not in str(exc_info.value)
