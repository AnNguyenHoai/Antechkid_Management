# -*- coding: utf-8 -*-
"""A4.8 release-gate regressions for active runtime/Git composition paths."""

from pathlib import Path

import centermanager.platform.synchronization.git_synchronization_provider as provider_module
from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.services.employee_document_service import EmployeeDocumentService


ROOT = Path(__file__).resolve().parents[1]
SYNC_INIT = ROOT / "src" / "centermanager" / "platform" / "synchronization" / "__init__.py"


class _CompletedProcess:
    returncode = 0
    stdout = ""
    stderr = ""


def test_active_git_provider_strips_credentials_before_subprocess_argv(tmp_path, monkeypatch):
    secret = "release-gate-secret-token"
    clean_url = "https://github.com/example/private-repo.git"
    provider = GitSynchronizationProvider(
        repo_path=tmp_path / "repository",
        repository_url=clean_url,
        token=secret,
        username="release-user",
        git_executable="git",
    )

    # clone() compatibility helper must never reconstruct a token-bearing URL.
    assert provider._build_authenticated_url() == clean_url

    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = list(cmd)
        captured["env"] = dict(kwargs.get("env") or {})
        return _CompletedProcess()

    monkeypatch.setattr(provider_module.subprocess, "run", fake_run)

    provider._run_git_command(
        ["ls-remote", f"https://{secret}@github.com/example/private-repo.git", "HEAD"],
        cwd=tmp_path,
    )

    argv = " ".join(str(part) for part in captured["cmd"])
    assert secret not in argv
    assert clean_url in argv
    assert captured["env"].get("CENTERMANAGER_GIT_TOKEN") == secret

    if provider._credential_helper is not None:
        provider._credential_helper.cleanup()


def test_active_sync_package_installs_credential_safety_before_other_git_wrappers():
    source = SYNC_INIT.read_text(encoding="utf-8")
    credential_pos = source.index("install_git_credential_safety(GitSynchronizationProvider)")
    origin_pos = source.index("install_origin_reconciliation(GitSynchronizationProvider)")
    serialization_pos = source.index("install_git_command_serialization(GitSynchronizationProvider)")
    assert credential_pos < origin_pos < serialization_pos


def test_employee_document_service_canonicalizes_legacy_plural_runtime_root(tmp_path):
    service = EmployeeDocumentService(lambda: None, tmp_path / "runtime" / "Attachments")
    assert service._attachments_root == tmp_path / "runtime" / "Attachment"
    assert service.get_runtime_employee_root("EMP-1") == (
        tmp_path / "runtime" / "Attachment" / "Employees" / "EMP-1"
    )
