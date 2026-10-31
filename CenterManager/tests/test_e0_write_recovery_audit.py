"""E0 characterizations, not safety guarantees or takeover implementation.

All Git remotes and encrypted data are synthetic and under tmp_path. Bad
behavior is asserted deliberately so the audit is reproducible on its base.
Replace these expectations with rejection tests when the approved fixes land.
"""
from datetime import datetime, timedelta
import importlib
import subprocess

import pytest

from centermanager.events.event_bus import EventBus
from centermanager.platform.collaboration import CollaborationManager
from centermanager.platform.collaboration.poller import CollaborationPoller
from centermanager.platform.synchronization import GitSynchronizationProvider
from centermanager.services.write_transaction import (
    WriteTransactionManager, WriteTransactionState,
)


def git(repo, *args, check=True):
    return subprocess.run(
        ["git", *args], cwd=repo, check=check, capture_output=True, text=True,
    )


@pytest.fixture
def clock(monkeypatch):
    class Clock(datetime):
        value = datetime(2026, 10, 31, 12, 0, 0)

        @classmethod
        def now(cls, tz=None):
            assert tz is None
            return cls.value

        @classmethod
        def at(cls, seconds):
            cls.value = datetime(2026, 10, 31, 12, 0, 0) + timedelta(seconds=seconds)

    for name in (
        "platform.synchronization.git_synchronization_provider",
        "platform.synchronization.lock_acquisition_diagnostics",
        "platform.synchronization.git_clock_skew_guard",
        "platform.collaboration.collaboration_manager",
        "platform.collaboration.false_waiting_guard",
        "platform.collaboration.finishing_authority_compat",
        "platform.collaboration.write_queue",
        "services.write_transaction",
    ):
        monkeypatch.setattr(importlib.import_module("centermanager." + name), "datetime", Clock)
    return Clock


@pytest.fixture
def machines(tmp_path, monkeypatch, clock):
    # Exercise the service/poller handlers deterministically; do not run real
    # heartbeat threads or long wall-clock sleeps in this characterization.
    heartbeat = importlib.import_module("centermanager.platform.collaboration.heartbeat")
    monkeypatch.setattr(heartbeat.HeartbeatManager, "start", lambda self: None)
    remote = tmp_path / "remote.git"
    remote.mkdir()
    git(remote, "init", "--bare")
    seed = tmp_path / "seed"
    seed.mkdir()
    git(seed, "init")
    git(seed, "config", "user.name", "E0 Synthetic")
    git(seed, "config", "user.email", "e0@example.invalid")
    (seed / "manifest.json").write_text('{"runtime_version": 1}\n', encoding="utf-8")
    git(seed, "add", ".")
    git(seed, "commit", "-m", "synthetic seed")
    git(seed, "branch", "-M", "main")
    git(seed, "remote", "add", "origin", str(remote))
    git(seed, "push", "origin", "main")
    clients = []

    def make(name, username=None):
        root = tmp_path / name
        root.mkdir()
        repo = root / "repository"
        git(tmp_path, "clone", "--branch", "main", str(remote), str(repo))
        provider = GitSynchronizationProvider(
            repo_path=repo, repository_url=str(remote), branch="main",
            allow_local_file_remote=True,
        )
        assert provider.connect()
        manager = CollaborationManager(runtime_root=root, event_bus=EventBus(), sync_provider=provider)
        manager.initialize(name, username or name, "admin")
        # Handoff DB synchronization is separately tested by the existing suite.
        manager.set_write_handoff_guard(lambda: True)
        clients.append(manager)
        return manager, provider

    yield make
    for manager in clients:
        manager.shutdown()


def handoff(manager):
    poller = CollaborationPoller(manager)
    poller._running = True
    poller._try_handoff_waiting_request(manager.get_lock_status(), manager.get_queue())
    poller._running = False


@pytest.mark.parametrize("crash_at,poll_phase,grant_at", [(0, 0, 660), (19, 1, 661), (39, 2, 662)])
def test_e0_killed_owner_queue_handoff_baseline(machines, clock, crash_at, poll_phase, grant_at):
    owner, provider = machines("owner")
    waiter, _ = machines("waiter")
    assert owner.request_write().is_granted
    assert provider._lease_duration_seconds == 60
    assert provider._clock_skew_tolerance_seconds == 600
    clock.at(crash_at)
    assert waiter.request_write().is_waiting
    # Simulated process kill: never call owner renewal or graceful shutdown.
    # Keep the surviving waiter alive on its normal 20-second refresh cadence.
    for second in range(crash_at + 20, grant_at, 20):
        clock.at(second)
        assert waiter.refresh_waiting_request()
    clock.at(659)
    handoff(waiter)
    assert not waiter.is_writing()
    clock.at(grant_at)
    handoff(waiter)
    assert waiter.is_writing()
    assert provider.remote_lock_status()["session_id"] == waiter.get_session_id()
    # Dead process' cached projection is still true: remote authority is unique,
    # process-local WRITE flags are not an end-to-end fencing proof.
    assert owner.is_writing()
    assert grant_at % 3 == poll_phase
    assert grant_at - crash_at in (660, 642, 623)


def test_e0_start_during_grace_returns_error_but_leaves_live_queue_entry(machines, clock):
    owner, _ = machines("owner")
    waiter, _ = machines("waiter")
    assert owner.request_write().is_granted
    clock.at(61)
    transaction = WriteTransactionManager(waiter)
    assert transaction.start_editing() is False
    assert transaction.state == WriteTransactionState.IDLE
    assert "clock-skew safety window" in transaction.last_start_error
    assert waiter.has_pending_waiting_request()
    # The still-live remote request may grant without the transaction in WAITING.
    for second in range(81, 660, 20):
        clock.at(second)
        assert waiter.refresh_waiting_request()
    clock.at(660)
    handoff(waiter)
    assert waiter.is_writing()
    transaction.on_write_granted()
    assert transaction.state == WriteTransactionState.IDLE


def test_e0_background_renewal_has_no_ui_progress_gate(machines, clock):
    owner, provider = machines("owner")
    assert owner.request_write().is_granted
    poller = CollaborationPoller(owner)
    poller._running = True
    try:
        # No UI event or user activity is supplied. The same worker callback is
        # used whether UI is responsive or blocked; this is not Windows UAT.
        for second in range(20, 121, 20):
            clock.at(second)
            poller._renew_active_lease()
        remote = provider.remote_lock_status()
        assert remote["lease_revision"] == 3
        assert datetime.fromisoformat(remote["lease_expires_at"]) == clock.now() + timedelta(seconds=60)
    finally:
        poller._running = False


def test_e0_same_username_old_session_can_release_new_session(machines):
    old, old_provider = machines("old", username="shared-user")
    new, new_provider = machines("new", username="shared-user")
    assert old.request_write().is_granted
    assert old_provider.release_lock("shared-user")
    assert new.request_write().is_granted
    assert new_provider.remote_lock_status()["session_id"] == new.get_session_id()
    # Real remote CAS succeeds: release checks username, not the caller session.
    assert old_provider.release_lock("shared-user")
    assert not new_provider.remote_lock_status()["locked"]


def test_e0_new_request_can_overtake_existing_queue_head(machines):
    owner, provider = machines("owner")
    first, _ = machines("first")
    newcomer, _ = machines("newcomer")
    assert owner.request_write().is_granted
    assert first.request_write().is_waiting
    assert provider.release_lock("owner")
    assert newcomer.request_write().is_granted
    assert first.get_queue()["next"]["session_id"] == first.get_session_id()


def test_e0_data_cas_accepts_old_writer_after_lock_handoff(machines):
    old, provider = machines("old")
    new, new_provider = machines("new")
    assert old.request_write().is_granted
    base = provider.get_remote_main_commit()
    assert provider.release_lock("old")
    assert new.request_write().is_granted
    # Model the gap after enter_finishing validation and before final data push.
    # Use the actual final provider push boundary; artifact validation/signing
    # happens earlier and does not make these two refs atomic.
    repo = provider._repo_path
    git(repo, "-c", "user.name=E0", "-c", "user.email=e0@example.invalid",
        "commit", "--allow-empty", "-m", "old writer paused then resumed")
    provider._push_only(expected_remote_commit=base)
    assert new_provider.get_remote_main_commit() == git(repo, "rev-parse", "HEAD").stdout.strip()
    assert new_provider.remote_lock_status()["session_id"] == new.get_session_id()


def test_e0_local_sqlcipher_commit_not_fenced_by_revoked_remote(machines, tmp_path):
    from centermanager.database.engine import create_engine_for_path
    from centermanager.platform.business.guard import WriteGuard
    from sqlalchemy import text

    old, provider = machines("old")
    new, _ = machines("new")
    assert old.request_write().is_granted
    assert provider.release_lock("old")
    assert new.request_write().is_granted
    old.suspend_write_lease_renewal()
    assert not old.ensure_write()
    assert WriteGuard(old).can_write()  # cached is_writing(), ignores suspension
    engine = create_engine_for_path(
        tmp_path / "synthetic.db", encrypted=True, encryption_key=b"a" * 32,
    )
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE synthetic_finance (amount INTEGER)"))
            conn.execute(text("INSERT INTO synthetic_finance VALUES (100)"))
        with engine.connect() as conn:
            assert conn.execute(text("SELECT amount FROM synthetic_finance")).scalar_one() == 100
    finally:
        engine.dispose()


def test_e0_lock_cas_rejects_stale_admin_snapshot(machines):
    owner, provider = machines("owner")
    assert owner.request_write().is_granted
    observed = provider._remote_lock_oid()
    assert provider.renew_lock("owner", owner.get_session_id())
    renewed = provider._remote_lock_oid()
    assert renewed != observed
    # Two admins using the same snapshot cannot delete a newly renewed lease.
    assert not provider._delete_lock_branch(expected_oid=observed)
    assert provider._remote_lock_oid() == renewed


def test_e0_atomic_two_ref_prototype_rejects_stale_publish(machines):
    """Protocol experiment only: production does NOT issue this atomic push.

    A changed lock and data ref must both be written, with exact old OIDs.
    Deployment also requires excluding all legacy/direct credential writers.
    """
    owner, provider = machines("owner")
    assert owner.request_write().is_granted
    lock_before = provider._remote_lock_oid()
    main_before = provider.get_remote_main_commit()
    assert provider.renew_lock("owner", owner.get_session_id())
    lock_after = provider._remote_lock_oid()
    proposed_lock = provider._read_lock_from_oid(lock_before)
    proposed_lock["lease_revision"] += 1
    proposed_lock["publish_intent"] = True
    candidate_lock = provider._create_lock_commit_plumbing(proposed_lock, lock_before)
    repo = provider._repo_path
    git(repo, "-c", "user.name=E0", "-c", "user.email=e0@example.invalid",
        "commit", "--allow-empty", "-m", "candidate data")
    result = git(repo, "push", "--atomic", "origin",
                 f"HEAD:refs/heads/main", f"{candidate_lock}:refs/heads/lock-main",
                 f"--force-with-lease=main:{main_before}",
                 f"--force-with-lease=lock-main:{lock_before}", check=False)
    assert result.returncode != 0
    assert provider.get_remote_main_commit() == main_before
    assert provider._remote_lock_oid() == lock_after


def test_e0_unreadable_lock_is_reported_as_absent(tmp_path, monkeypatch):
    provider = GitSynchronizationProvider(repo_path=tmp_path / "repo")
    monkeypatch.setattr(provider, "_remote_lock_oid", lambda: "unreadable-oid")
    monkeypatch.setattr(provider, "_read_lock_from_oid", lambda oid: {})
    assert provider.remote_lock_status() == {"locked": False, "owner": None, "session_id": None}
