"""Isolated real-Git publication fencing probes.

No network, GitHub credentials, CenterManager runtime, or production database.
The opt-in release-gate probe intentionally FAILS when a legacy client can
directly publish after another client changes WRITE ownership.
Run:
  python -m pytest tests/test_qa_p0_git_publication_fencing.py -v
  ANTECHKIDS_QA_FENCING_GATE=1 python -m pytest tests/test_qa_p0_git_publication_fencing.py -v
"""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def _git(cwd: Path, *args: str, check: bool = True):
    result = subprocess.run(
        ["git", *args], cwd=cwd, text=True, capture_output=True,
        timeout=30, check=False,
        env={**os.environ, "GIT_CONFIG_NOSYSTEM": "1",
             "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0"},
    )
    if check and result.returncode:
        raise AssertionError(
            f"git {args!r} exited {result.returncode}: {result.stderr}"
        )
    return result


def _commit(repo: Path, name: str, value: str):
    (repo / name).write_text(value, encoding="utf-8")
    _git(repo, "add", name)
    _git(repo, "commit", "-m", f"synthetic {value}")
    return _git(repo, "rev-parse", "HEAD").stdout.strip()


@pytest.fixture
def independent_clients(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("Git binary is required")
    remote = tmp_path / "isolated-authority.git"
    remote.mkdir()
    _git(remote, "init", "--bare")
    a = tmp_path / "client-a"
    a.mkdir()
    _git(a, "init")
    _git(a, "config", "user.name", "QA Client A")
    _git(a, "config", "user.email", "a@example.invalid")
    _commit(a, "business.txt", "accepted-base")
    _git(a, "branch", "-M", "main")
    _git(a, "remote", "add", "origin", str(remote))
    _git(a, "push", "origin", "main")
    _git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    b = tmp_path / "client-b"
    _git(tmp_path, "clone", str(remote), str(b))
    _git(b, "config", "user.name", "QA Client B")
    _git(b, "config", "user.email", "b@example.invalid")
    assert _git(a, "rev-parse", "HEAD").stdout == _git(b, "rev-parse", "HEAD").stdout
    return remote, a, b


def _remote_oid(remote: Path, ref: str):
    return _git(remote, "rev-parse", ref).stdout.strip()


def test_git_expected_oid_rejects_stale_competing_publication(independent_clients):
    """A compare-and-swap push must not overwrite a newer accepted MAIN."""
    remote, a, b = independent_clients
    base = _remote_oid(remote, "refs/heads/main")
    a_head = _commit(a, "a.txt", "machine-a")
    _git(a, "push", "origin", "main")
    assert _remote_oid(remote, "refs/heads/main") == a_head
    _commit(b, "b.txt", "machine-b")
    attempt = _git(
        b, "push", f"--force-with-lease=refs/heads/main:{base}",
        "origin", "HEAD:refs/heads/main", check=False
    )
    assert attempt.returncode != 0, "Stale OID unexpectedly overwrote MAIN"
    assert _remote_oid(remote, "refs/heads/main") == a_head


def test_independent_clone_has_distinct_git_repository(independent_clients):
    """Test fixture must not share a local Git index, HEAD or working tree."""
    remote, a, b = independent_clients
    _commit(a, "local-only.txt", "private-A")
    assert not (b / "local-only.txt").exists()
    assert _remote_oid(remote, "refs/heads/main") == _git(b, "rev-parse", "HEAD").stdout.strip()
    assert _git(a, "rev-parse", "HEAD").stdout.strip() != _git(b, "rev-parse", "HEAD").stdout.strip()


@pytest.mark.skipif(
    os.getenv("ANTECHKIDS_QA_FENCING_GATE") != "1",
    reason="Opt-in release gate: expected to fail on an unprotected legacy-compatible remote",
)
def test_revoked_legacy_client_must_not_publish_directly(independent_clients):
    """P0 RELEASE GATE: rejected legacy direct MAIN push after ownership handoff.

    This probes remote ENFORCEMENT, not client cooperation. The isolated bare
    remote models one accepting ordinary authorized Git pushes; it is NOT a
    claim about currently configured production GitHub branch protection.
    """
    remote, old, successor = independent_clients
    # The successor changes only the authority ref, not MAIN. The retired
    # client has an up-to-date MAIN base and still has Git push capability.
    lock_base = _remote_oid(remote, "refs/heads/main")
    _git(successor, "checkout", "-b", "lock-main", lock_base)
    lock_head = _commit(successor, "owner.json", '{"session":"successor"}')
    _git(successor, "push", "origin", "lock-main:refs/heads/lock-main")
    assert _remote_oid(remote, "refs/heads/lock-main") == lock_head
    accepted_main_before = _remote_oid(remote, "refs/heads/main")
    _git(old, "checkout", "main")
    stale_head = _commit(old, "unaccepted-business.txt", "stale-legacy-write")
    push = _git(old, "push", "origin", "main:refs/heads/main", check=False)
    accepted_main_after = _remote_oid(remote, "refs/heads/main")
    assert push.returncode != 0 and accepted_main_after == accepted_main_before, (
        "P0 publication fencing absent on this isolated remote: retired client "
        f"direct push exited={push.returncode}, MAIN before={accepted_main_before}, "
        f"after={accepted_main_after}, stale_commit={stale_head}. "
        "Enforce server-side owner/epoch authorization and deny legacy credentials."
    )
