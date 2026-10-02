# -*- coding: utf-8 -*-
"""Regression coverage for P2/P3 Git transport and credential hardening."""

from pathlib import Path

import pytest

from centermanager.core.git_url_safety import (
    RepositoryUrlPolicyError,
    validate_repository_url,
)
from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.services.git_config_service import GitConfig


@pytest.mark.parametrize(
    "url",
    [
        "http://github.com/example/repo.git",
        "ssh://git@github.com/example/repo.git",
        "git@github.com:example/repo.git",
        "https://secret@github.com/example/repo.git",
        "https://user:secret@github.com/example/repo.git",
    ],
)
def test_repository_url_policy_rejects_non_https_or_embedded_credentials(url):
    with pytest.raises(RepositoryUrlPolicyError):
        validate_repository_url(url)


def test_repository_url_policy_accepts_credential_free_https():
    url = "https://github.com/example/repo.git"
    assert validate_repository_url(url) == url


def test_file_remote_requires_explicit_opt_in():
    url = Path("/tmp/authoritative.git").resolve().as_uri()
    with pytest.raises(RepositoryUrlPolicyError):
        validate_repository_url(url)
    assert validate_repository_url(url, allow_local_file_remote=True) == url


def test_absolute_local_path_requires_explicit_opt_in(tmp_path):
    local_path = str((tmp_path / "authoritative.git").resolve())
    with pytest.raises(RepositoryUrlPolicyError):
        validate_repository_url(local_path)
    assert (
        validate_repository_url(local_path, allow_local_file_remote=True)
        == local_path
    )


def test_git_config_persists_local_remote_exception_only_when_explicit():
    url = Path("/tmp/authoritative.git").resolve().as_uri()
    config = GitConfig(
        repository_url=url,
        username="sec06-uat",
        token="local-fixture-credential",
        allow_local_file_remote=True,
    )
    serialized = config.to_dict()
    assert serialized["repository_url"] == url
    assert serialized["allow_local_file_remote"] is True


def test_provider_never_builds_token_bearing_remote_url(tmp_path):
    url = "https://github.com/example/repo.git"
    secret = "service-secret-must-not-enter-url"
    provider = GitSynchronizationProvider(
        repo_path=tmp_path / "repo",
        repository_url=url,
        token=secret,
        username="center-manager-service",
        branch="main",
    )

    clone_url = provider._build_authenticated_url()
    assert clone_url == url
    assert secret not in clone_url


def test_provider_rejects_file_remote_without_explicit_uat_opt_in(tmp_path):
    file_url = (tmp_path / "authoritative.git").resolve().as_uri()
    with pytest.raises(RepositoryUrlPolicyError):
        GitSynchronizationProvider(
            repo_path=tmp_path / "repo",
            repository_url=file_url,
            token="local-fixture-credential",
            username="sec06-uat",
        )


def test_provider_accepts_file_remote_with_explicit_uat_opt_in(tmp_path):
    file_url = (tmp_path / "authoritative.git").resolve().as_uri()
    provider = GitSynchronizationProvider(
        repo_path=tmp_path / "repo",
        repository_url=file_url,
        token="local-fixture-credential",
        username="sec06-uat",
        allow_local_file_remote=True,
    )
    assert provider._repository_url == file_url
