"""QA-P0-02: adversarial direct-Git publisher tests on disposable bare remote.

These probes demonstrate the difference between MAIN CAS and remote authority
enforcement. The unprotected-remote attack MUST succeed (a vulnerability model),
and must never be mistaken for a production-equivalent security pass.
"""
from pathlib import Path
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
import pytest


def git(where, *args, check=True):
    p = subprocess.run(["git", *args], cwd=where, text=True,
                       capture_output=True, timeout=45, check=False)
    if check and p.returncode:
        raise AssertionError(f"git {args}: {p.stderr}")
    return p


def oid(where, ref):
    return git(where, "rev-parse", ref).stdout.strip()


def commit(where, filename, contents):
    (where / filename).write_text(contents, encoding="utf-8")
    git(where, "add", filename)
    git(where, "commit", "-m", "qa synthetic " + filename)
    return oid(where, "HEAD")


@pytest.fixture
def r1(tmp_path):
    if not shutil.which("git"):
        pytest.skip("git unavailable")
    remote = tmp_path / "remote.git"
    remote.mkdir()
    git(remote, "init", "--bare")
    a = tmp_path / "a"
    a.mkdir()
    git(a, "init")
    git(a, "config", "user.name", "QA A")
    git(a, "config", "user.email", "a@example.invalid")
    commit(a, "business.txt", "synthetic student S-001")
    git(a, "branch", "-M", "main")
    git(a, "remote", "add", "origin", str(remote))
    git(a, "push", "origin", "main")
    git(remote, "symbolic-ref", "HEAD", "refs/heads/main")
    b = tmp_path / "b"
    git(tmp_path, "clone", str(remote), str(b))
    git(b, "config", "user.name", "QA B")
    git(b, "config", "user.email", "b@example.invalid")
    return remote, a, b


@pytest.mark.parametrize("reason", ["expired", "revoked", "same-username", "read-only", "legacy"])
def test_r1_direct_publisher_bypasses_unrelated_authority_ref(r1, reason):
    """PUB-FENCE-001/002/003/004/016: R1 should expose this bypass."""
    remote, a, b = r1
    old_main = oid(remote, "refs/heads/main")
    git(b, "checkout", "-b", "lock-main")
    successor_lock = commit(b, "authority.txt", "current-owner=B; old=" + reason)
    git(b, "push", "origin", "lock-main:refs/heads/lock-main")
    # A deliberately calls Git directly, not the modern collaboration API.
    candidate = commit(a, "stale-" + reason + ".txt", "unaccepted A")
    result = git(a, "push", "origin", "main:refs/heads/main", check=False)
    assert result.returncode == 0, result.stderr
    assert oid(remote, "refs/heads/main") == candidate != old_main
    assert oid(remote, "refs/heads/lock-main") == successor_lock
    # Demonstration of failure of ownership enforcement, NOT a product PASS.


def test_r1_main_cas_rejects_stale_oid(r1):
    """PUB-FENCE-005: MAIN CAS prevents overwriting a newer MAIN."""
    remote, a, b = r1
    old = oid(remote, "refs/heads/main")
    accepted = commit(b, "b.txt", "new-main")
    git(b, "push", "origin", "main")
    candidate = commit(a, "a.txt", "old-main-offline")
    attempt = git(a, "push", f"--force-with-lease=refs/heads/main:{old}",
                  "origin", "HEAD:refs/heads/main", check=False)
    assert attempt.returncode != 0
    assert oid(remote, "refs/heads/main") == accepted
    assert oid(a, "HEAD") == candidate


def test_r1_lease_unchanged_main_does_not_stop_direct_push(r1):
    """PUB-FENCE-006: fresh MAIN is NOT a proof of valid lease."""
    remote, a, b = r1
    unchanged_main = oid(remote, "refs/heads/main")
    git(b, "checkout", "-b", "lock-main")
    new_lock = commit(b, "owner.txt", "B takes WRITE")
    git(b, "push", "origin", "lock-main")
    old = commit(a, "obsolete-owner.txt", "A old session")
    result = git(a, "push", "origin", "main", check=False)
    assert result.returncode == 0, result.stderr
    assert oid(remote, "refs/heads/main") == old != unchanged_main
    assert oid(remote, "refs/heads/lock-main") == new_lock


def test_r1_lost_ack_reconcile_by_remote_oid(r1):
    """PUB-FENCE-011/014: accepted push with no app ACK is not a failed push."""
    remote, a, b = r1
    candidate = commit(a, "receipt.txt", "synthetic finance I-001")
    git(a, "push", "origin", "main")
    app_ack = None  # simulated lost response *after* remote acceptance
    assert app_ack is None
    assert oid(remote, "refs/heads/main") == candidate
    assert git(a, "push", "origin", "main", check=False).returncode == 0
    assert oid(remote, "refs/heads/main") == candidate


def test_r1_concurrent_direct_publishers_only_git_cas_not_ownership(r1):
    """PUB-FENCE-007: only one MAIN FF succeeds for divergent candidates."""
    remote, a, b = r1
    ca = commit(a, "a.txt", "A")
    cb = commit(b, "b.txt", "B")
    barrier = threading.Barrier(2)
    def push(path):
        barrier.wait(timeout=10)
        return git(path, "push", "origin", "main", check=False).returncode
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(push, p) for p in (a, b)]
        result = [f.result(timeout=90) for f in futures]
    assert sorted(result) == [0, 1], result
    assert oid(remote, "refs/heads/main") in {ca, cb}
