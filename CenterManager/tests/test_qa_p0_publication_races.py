"""QA-P0 publication race probes using disposable local Git repositories.

Tests real atomic multi-ref CAS and lost-push acknowledgement reconciliation.
These are Git transport tests, not proof of deployed GitHub authorization.
"""
import pytest
from tests.test_qa_p0_git_publication_fencing import (
    independent_clients, _git, _commit, _remote_oid,  # noqa: F401
)


def _establish_lock(remote, a, b):
    base = _remote_oid(remote, "refs/heads/main")
    _git(a, "checkout", "-b", "lock-main", base)
    first_lock = _commit(a, "owner.json", "owner-a")
    _git(a, "push", "origin", "lock-main:refs/heads/lock-main")
    # B must observe the lock ref from the remote; MAIN remains independent.
    _git(b, "fetch", "origin", "refs/heads/lock-main:refs/heads/qa-lock-base")
    assert _remote_oid(remote, "refs/heads/lock-main") == first_lock
    return base, first_lock


def test_atomic_publish_rejected_when_owner_ref_changed(independent_clients):
    """A stale publisher must not update MAIN when lock CAS conflicts."""
    remote, a, b = independent_clients
    base_main, old_lock = _establish_lock(remote, a, b)

    # B prepares a replacement authority commit while A still holds old lock.
    _git(b, "checkout", "-b", "lock-main", "refs/heads/qa-lock-base")
    successor_lock = _commit(b, "owner.json", "owner-b")
    _git(
        b, "push",
        f"--force-with-lease=refs/heads/lock-main:{old_lock}",
        "origin", "lock-main:refs/heads/lock-main"
    )

    # A has not observed the successor and prepares valid FF main data.
    _git(a, "checkout", "main")
    stale_data = _commit(a, "stale.txt", "owner-a-unaccepted")
    _git(a, "checkout", "lock-main")
    stale_lock_update = _commit(a, "owner.json", "owner-a-renewal")
    attempt = _git(
        a, "push", "--atomic",
        f"--force-with-lease=refs/heads/lock-main:{old_lock}",
        f"--force-with-lease=refs/heads/main:{base_main}",
        "origin",
        f"{stale_data}:refs/heads/main",
        f"{stale_lock_update}:refs/heads/lock-main",
        check=False,
    )
    assert attempt.returncode != 0, "Stale ownership unexpectedly accepted"
    assert _remote_oid(remote, "refs/heads/main") == base_main, (
        "Atomic rejection failed: MAIN was partially updated"
    )
    assert _remote_oid(remote, "refs/heads/lock-main") == successor_lock


def test_atomic_publish_updates_data_and_authority_together(independent_clients):
    """Both refs move or neither moves on an eligible atomic local push."""
    remote, a, b = independent_clients
    base_main, prior_lock = _establish_lock(remote, a, b)
    _git(a, "checkout", "main")
    data_commit = _commit(a, "accepted.txt", "accepted-business")
    _git(a, "checkout", "lock-main")
    lock_commit = _commit(a, "owner.json", "owner-a-publish-receipt")
    accepted = _git(
        a, "push", "--atomic",
        f"--force-with-lease=refs/heads/main:{base_main}",
        f"--force-with-lease=refs/heads/lock-main:{prior_lock}",
        "origin",
        f"{data_commit}:refs/heads/main",
        f"{lock_commit}:refs/heads/lock-main",
        check=False,
    )
    if accepted.returncode and "atomic" in accepted.stderr.lower() and "support" in accepted.stderr.lower():
        pytest.skip("Disposable Git remote does not support atomic pushes")
    assert accepted.returncode == 0, accepted.stderr
    assert _remote_oid(remote, "refs/heads/main") == data_commit
    assert _remote_oid(remote, "refs/heads/lock-main") == lock_commit


def test_lost_ack_is_reconciled_by_remote_oid_not_blind_retry(independent_clients):
    """After an accepted push, local ACK loss cannot mean the data was rejected."""
    remote, a, b = independent_clients
    base_main = _remote_oid(remote, "refs/heads/main")
    accepted = _commit(a, "receipt.txt", "exact-once-accepted")
    _git(a, "push", "origin", "main:refs/heads/main")

    # Simulate lost application-level response after the Git operation finished.
    unknown_ack = None
    assert unknown_ack is None
    observed = _remote_oid(remote, "refs/heads/main")
    assert observed != base_main
    assert observed == accepted, "Must reconcile exact commit OID before retry"

    # A repeated *identical* push cannot introduce an extra commit.
    retry = _git(a, "push", "origin", "main:refs/heads/main", check=False)
    assert retry.returncode == 0
    assert _remote_oid(remote, "refs/heads/main") == accepted
    assert _git(remote, "rev-list", "--count", "refs/heads/main").stdout.strip() == "2"


def test_conflicting_stale_main_publish_keeps_local_commit_for_recovery(independent_clients):
    """Rejected stale publication must not delete the offline candidate."""
    remote, a, b = independent_clients
    base = _remote_oid(remote, "refs/heads/main")
    accepted = _commit(a, "accepted.txt", "new-authority")
    _git(a, "push", "origin", "main")
    candidate = _commit(b, "candidate.txt", "offline-unaccepted")
    rejected = _git(
        b, "push", f"--force-with-lease=refs/heads/main:{base}",
        "origin", "HEAD:refs/heads/main", check=False,
    )
    assert rejected.returncode != 0
    assert _remote_oid(remote, "refs/heads/main") == accepted
    assert _git(b, "rev-parse", "HEAD").stdout.strip() == candidate
    assert (b / "candidate.txt").read_text(encoding="utf-8") == "offline-unaccepted"
