"""Operation-local reuse must reduce Git calls without reusing stale authority."""
from datetime import timedelta
import logging
import subprocess

import pytest

from tests.test_e0_write_recovery_audit import machines, clock  # noqa: F401


def trace_commands(monkeypatch, provider):
    commands = []
    original = provider._run_git_command

    def run(args, *positional, **kwargs):
        commands.append(tuple(args))
        return original(args, *positional, **kwargs)

    monkeypatch.setattr(provider, "_run_git_command", run)
    return commands


def test_validation_reads_lock_once_and_next_validation_observes_loss(machines, monkeypatch):
    owner, provider = machines("owner")
    successor, _ = machines("successor")
    assert owner.request_write().is_granted
    commands = trace_commands(monkeypatch, provider)
    session = owner.get_session()

    result = owner.validate_write_authority(session)

    assert result["valid"]
    assert result["generation_authoritative"]
    assert result["finishing_deadline_authoritative"]
    assert result["finishing_deadline"] is None
    assert commands.count(("ls-remote", "origin", "refs/heads/lock-main")) == 1
    assert owner._lock.get_lock_info()["session_id"] == session.session_id

    assert owner.release_write()
    assert successor.request_write().is_granted
    commands.clear()
    result = owner.validate_write_authority(session)
    assert not result["valid"]
    assert "owner mismatch" in result["reason"].lower()
    assert commands.count(("ls-remote", "origin", "refs/heads/lock-main")) == 1


@pytest.mark.parametrize("deadline_offset,valid", [(120, True), (-1, False)])
def test_deadline_is_checked_from_same_fresh_lock(machines, clock, monkeypatch, deadline_offset, valid):
    owner, provider = machines("owner")
    assert owner.request_write().is_granted
    oid = provider._remote_lock_oid()
    record = provider._read_lock_from_oid(oid)
    deadline = clock.now() + timedelta(seconds=deadline_offset)
    record["finishing_deadline"] = deadline.isoformat()
    record["finishing_started_at"] = clock.now().isoformat()
    record["publish_intent"] = True
    candidate = provider._create_lock_commit_plumbing(record, oid)
    assert provider._push_lock_branch(candidate, oid)
    commands = trace_commands(monkeypatch, provider)

    result = owner.validate_write_authority(owner.get_session())

    assert result["valid"] is valid
    assert result["finishing_deadline"] == deadline
    assert commands.count(("ls-remote", "origin", "refs/heads/lock-main")) == 1


def test_validation_does_not_reuse_authority_during_remote_outage(machines, monkeypatch):
    owner, provider = machines("owner")
    assert owner.request_write().is_granted
    assert owner.validate_write_authority(owner.get_session())["valid"]
    monkeypatch.setattr(provider, "remote_lock_status", lambda: {
        "state": "UNKNOWN", "error": "unavailable", "locked": False,
    })
    result = owner.validate_write_authority(owner.get_session())
    assert not result["valid"]
    assert "unknown" in result["reason"].lower()


def test_renewal_reuses_object_but_keeps_remote_cas_and_readback(machines, monkeypatch):
    owner, provider = machines("owner")
    assert owner.request_write().is_granted
    old_oid = provider._remote_lock_oid()
    commands = trace_commands(monkeypatch, provider)

    assert provider.renew_lock(owner.get_session().username, owner.get_session_id())

    assert not any(cmd[0] == "fetch" for cmd in commands)
    assert commands.count(("ls-remote", "origin", "refs/heads/lock-main")) == 2
    assert any(f"--force-with-lease=lock-main:{old_oid}" in cmd for cmd in commands)
    assert provider.remote_lock_status()["lease_revision"] == 1


def test_cold_lock_reader_fetches_and_refuses_live_owner(machines, monkeypatch):
    owner, provider = machines("owner")
    contender, cold = machines("contender")
    assert owner.request_write().is_granted
    commands = trace_commands(monkeypatch, cold)

    assert not cold.acquire_lock(contender._build_lock_data())
    assert commands.count(("fetch", "origin", "lock-main")) == 1
    assert cold.last_lock_failure_was_contention()
    commands.clear()
    assert not cold.acquire_lock(contender._build_lock_data())
    assert not any(cmd[0] == "fetch" for cmd in commands)
    assert ("ls-remote", "origin", "refs/heads/lock-main") in commands
    assert provider.remote_lock_status()["session_id"] == owner.get_session_id()


def test_missing_lock_object_fetch_failure_never_grants(machines, monkeypatch):
    owner, provider = machines("owner")
    contender, cold = machines("contender")
    assert owner.request_write().is_granted
    monkeypatch.setattr(cold, "_fetch_lock_branch", lambda: False)
    assert not cold.acquire_lock(contender._build_lock_data())
    assert not cold.last_lock_failure_was_contention()
    assert provider.remote_lock_status()["session_id"] == owner.get_session_id()


def test_queue_refresh_skips_known_object_fetch_and_retains_other_waiters(machines, monkeypatch):
    owner, _ = machines("owner")
    waiter, provider = machines("waiter")
    other, _ = machines("other")
    assert owner.request_write().is_granted
    assert waiter.request_write().is_waiting
    commands = trace_commands(monkeypatch, provider)
    assert waiter.refresh_waiting_request()
    assert not any(cmd[0] == "fetch" for cmd in commands)

    assert other.request_write().is_waiting
    commands.clear()
    assert waiter.refresh_waiting_request()
    assert commands.count(("fetch", "origin", "queue-main")) == 1
    sessions = {item["session_id"] for item in provider.remote_queue_status()["requests"]}
    assert sessions == {waiter.get_session_id(), other.get_session_id()}


def test_git_perf_logs_preserve_failure_without_logging_arguments(machines, monkeypatch, caplog):
    _, provider = machines("client")
    secret = "private-argument-not-for-perf"

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("git", 15)

    monkeypatch.setattr(subprocess, "run", timeout)
    with caplog.at_level(logging.DEBUG):
        with pytest.raises(subprocess.TimeoutExpired):
            provider._run_git_command(["ls-remote", "origin", secret], timeout=15)
    messages = [r.getMessage() for r in caplog.records if r.getMessage().startswith("PERF git")]
    assert len(messages) == 1
    assert "command=ls-remote" in messages[0]
    assert "lock_wait_ms=" in messages[0] and "run_ms=" in messages[0]
    assert "outcome=error" in messages[0]
    assert secret not in messages[0]
