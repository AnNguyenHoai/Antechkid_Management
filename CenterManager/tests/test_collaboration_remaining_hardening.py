# -*- coding: utf-8 -*-
"""Regression tests for remaining collaboration hardening."""
from datetime import datetime, timedelta
from pathlib import Path

from centermanager.platform.synchronization.git_synchronization_provider import (
    GitSynchronizationProvider,
)


def _provider_without_git(tmp_path: Path) -> GitSynchronizationProvider:
    provider = object.__new__(GitSynchronizationProvider)
    provider._connected = True
    provider._offline = False
    provider._repo_path = tmp_path
    provider._queue_request_ttl_seconds = 120
    provider._queue_clock_skew_tolerance_seconds = 60
    provider._collaboration_git_timeout_seconds = 15
    return provider


def test_health_requires_authoritative_remote_reachability(tmp_path):
    provider = _provider_without_git(tmp_path)
    calls = []

    def fake_run(args, **kwargs):
        calls.append((list(args), dict(kwargs)))
        if args[0] == "version":
            return "git version test"
        raise RuntimeError("remote unavailable")

    provider._run_git_command = fake_run

    assert provider.health() is False
    assert provider._offline is True
    assert calls[1][0] == ["fetch", "origin", "--dry-run"]
    assert calls[1][1]["timeout"] == 15


def test_remote_queue_fifo_uses_authoritative_sequence_not_machine_clock(tmp_path):
    provider = _provider_without_git(tmp_path)
    now = datetime.now()

    # Machine B requested first but its wall clock is five minutes ahead.
    first = {
        "request_id": "first",
        "session_id": "b",
        "priority": 100,
        "status": "pending",
        "timestamp": (now + timedelta(minutes=5)).isoformat(),
        "enqueue_timestamp": (now + timedelta(minutes=5)).isoformat(),
        "queue_sequence": 1,
    }
    # Machine C requested later but its clock is five minutes behind.
    second = {
        "request_id": "second",
        "session_id": "c",
        "priority": 100,
        "status": "pending",
        "timestamp": (now - timedelta(minutes=5)).isoformat(),
        "enqueue_timestamp": (now - timedelta(minutes=5)).isoformat(),
        "queue_sequence": 2,
    }

    ordered = provider._filter_live_queue_requests([second, first])
    assert [item["request_id"] for item in ordered] == ["first", "second"]


def test_remote_queue_expiry_has_bounded_clock_skew_grace(tmp_path):
    provider = _provider_without_git(tmp_path)
    now = datetime.now()

    inside_grace = {
        "request_id": "inside",
        "session_id": "b",
        "priority": 100,
        "status": "pending",
        "timestamp": (now - timedelta(seconds=150)).isoformat(),
        "enqueue_timestamp": now.isoformat(),
        "queue_sequence": 1,
    }
    beyond_grace = {
        "request_id": "expired",
        "session_id": "c",
        "priority": 100,
        "status": "pending",
        "timestamp": (now - timedelta(seconds=181)).isoformat(),
        "enqueue_timestamp": now.isoformat(),
        "queue_sequence": 2,
    }

    live = provider._filter_live_queue_requests([inside_grace, beyond_grace])
    assert [item["request_id"] for item in live] == ["inside"]


def test_remote_enqueue_assigns_sequence_inside_cas_mutation(tmp_path):
    provider = _provider_without_git(tmp_path)
    captured = {}

    def fake_mutate(mutator, retries=5):
        requests = [
            {
                "request_id": "legacy",
                "session_id": "a",
                "priority": 100,
                "status": "pending",
                "timestamp": datetime.now().isoformat(),
                "enqueue_timestamp": datetime.now().isoformat(),
            }
        ]
        changed, result = mutator(requests)
        captured["changed"] = changed
        captured["requests"] = result
        return True

    provider._mutate_remote_queue = fake_mutate

    assert provider.enqueue_remote_write_request(
        {
            "request_id": "new",
            "session_id": "b",
            "priority": 100,
            "status": "pending",
            "timestamp": datetime.now().isoformat(),
            "enqueue_timestamp": datetime.now().isoformat(),
        }
    )

    assert captured["changed"] is True
    assert captured["requests"][0]["queue_sequence"] == 1
    assert captured["requests"][1]["queue_sequence"] == 2


def test_collaboration_commands_pass_bounded_timeout_contract():
    provider_source = Path(
        "src/centermanager/platform/synchronization/git_synchronization_provider.py"
    ).read_text(encoding="utf-8")
    output_safety_source = Path(
        "src/centermanager/platform/synchronization/git_output_safety.py"
    ).read_text(encoding="utf-8")
    diagnostics_source = Path(
        "src/centermanager/platform/synchronization/lock_acquisition_diagnostics.py"
    ).read_text(encoding="utf-8")

    assert "self._collaboration_git_timeout_seconds = 15" in provider_source
    assert "timeout=self._collaboration_git_timeout_seconds" in provider_source
    assert "timeout=timeout" in output_safety_source
    assert "timeout=self._collaboration_git_timeout_seconds" in diagnostics_source
