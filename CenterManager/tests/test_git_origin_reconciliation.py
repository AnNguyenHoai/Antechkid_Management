# -*- coding: utf-8 -*-
"""Regression tests for Git origin canonicalization and connect()."""

import json
from pathlib import Path

import git

from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.platform.synchronization.git_origin_reconciliation import (
    _normalize_remote_url,
)


def _seed_bare_remote(remote: Path) -> tuple[Path, str]:
    source = remote.parent / f"{remote.stem}-source"
    source.mkdir()
    repo = git.Repo.init(source)
    manifest = source / "manifest.json"
    manifest.write_text(json.dumps({"runtime_version": 1}), encoding="utf-8")
    repo.index.add([str(manifest)])
    repo.index.commit("Initial commit")
    branch = repo.active_branch.name

    git.Repo.init(remote, bare=True)
    origin = repo.create_remote("origin", str(remote))
    origin.push(refspec=f"{branch}:{branch}")
    return source, branch


def test_normalize_windows_local_paths_are_equivalent():
    assert _normalize_remote_url(r"C:\Work\remote.git") == _normalize_remote_url(
        "c:/work/remote"
    )


def test_normalize_file_url_matches_windows_local_path():
    assert _normalize_remote_url("file:///C:/Work/remote.git") == _normalize_remote_url(
        r"C:\Work\remote"
    )


def test_normalize_network_remotes_without_filesystem_semantics():
    assert _normalize_remote_url("HTTPS://GitHub.com/Org/Repo.git/") == (
        "https://github.com/org/repo"
    )
    assert _normalize_remote_url("git@GitHub.com:Org/Repo.git") == (
        "git@github.com:org/repo"
    )


def test_connect_accepts_equivalent_local_origin(tmp_path):
    remote = tmp_path / "remote.git"
    _source, branch = _seed_bare_remote(remote)
    clone_path = tmp_path / "clone"
    provider = GitSynchronizationProvider(
        repo_path=clone_path,
        repository_url=str(remote).replace("\\", "/"),
        token="",
        branch=branch,
    )

    assert provider.connect() is True
    assert provider.health() is True


def test_connect_reconciles_a_different_origin(tmp_path):
    remote_a = tmp_path / "remote-a.git"
    remote_b = tmp_path / "remote-b.git"
    _source_a, branch = _seed_bare_remote(remote_a)
    _source_b, _branch_b = _seed_bare_remote(remote_b)

    clone_path = tmp_path / "clone"
    provider = GitSynchronizationProvider(
        repo_path=clone_path,
        repository_url=str(remote_a),
        token="",
        branch=branch,
    )
    assert provider.connect() is True

    provider._repository_url = str(remote_b)
    assert provider.connect() is True
    assert _normalize_remote_url(provider._repo.remote("origin").url) == _normalize_remote_url(
        str(remote_b)
    )
