import subprocess
from types import SimpleNamespace

import centermanager.platform.synchronization.git_output_safety as output_safety


def test_non_windows_does_not_add_process_window_options(monkeypatch):
    monkeypatch.setattr(output_safety.os, "name", "posix")
    assert output_safety._windows_hidden_process_kwargs() == {}


def test_windows_requests_no_console_and_hidden_startup(monkeypatch):
    class FakeStartupInfo:
        def __init__(self):
            self.dwFlags = 0
            self.wShowWindow = None

    monkeypatch.setattr(output_safety.os, "name", "nt")
    monkeypatch.setattr(output_safety.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    monkeypatch.setattr(output_safety.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(output_safety.subprocess, "SW_HIDE", 0, raising=False)
    monkeypatch.setattr(output_safety.subprocess, "STARTUPINFO", FakeStartupInfo, raising=False)

    kwargs = output_safety._windows_hidden_process_kwargs()
    assert kwargs["creationflags"] == 0x08000000
    assert kwargs["startupinfo"].dwFlags & 1
    assert kwargs["startupinfo"].wShowWindow == 0


def test_git_runner_forwards_hidden_windows_options(monkeypatch, tmp_path):
    class Provider:
        _repo_path = tmp_path
        _git_executable = "git.exe"
        _offline = False

        def _get_env(self):
            return {}

    monkeypatch.setattr(
        output_safety,
        "_windows_hidden_process_kwargs",
        lambda: {"creationflags": 1234, "startupinfo": "hidden"},
    )
    seen = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen.update(kwargs)
        return SimpleNamespace(returncode=0, stdout=b"ok\n", stderr=b"")

    monkeypatch.setattr(subprocess, "run", fake_run)
    output_safety.install_git_output_safety(Provider)

    provider = Provider()
    assert provider._run_git_command(["status"]) == "ok"
    assert seen["creationflags"] == 1234
    assert seen["startupinfo"] == "hidden"
    assert seen["text"] is False
    assert seen["capture_output"] is True
