"""Queue push outcomes must not be called CAS races without remote evidence."""
from types import SimpleNamespace
import pytest

from centermanager.platform.synchronization import GitSynchronizationProvider


@pytest.mark.parametrize("observed,expected,accepted,kind", [
    ("new-commit", "old-commit", True, "VERIFIED"),
    ("another-commit", "old-commit", False, "CONTENTION"),
    ("old-commit", "old-commit", False, "GIT_FAILURE"),
])
def test_queue_push_error_classifies_actual_remote_ref(
    observed, expected, accepted, kind
):
    provider = SimpleNamespace(
        _queue_branch="queue-main",
        _collaboration_git_timeout_seconds=15,
        _run_git_command=lambda *args, **kwargs: (_ for _ in ()).throw(
            TimeoutError("push took too long")
        ),
        _remote_queue_oid=lambda: observed,
    )
    result = GitSynchronizationProvider._push_queue_branch(
        provider, "new-commit", expected
    )
    assert result is accepted
    assert provider._last_queue_publication_outcome == kind


def test_queue_push_unknown_does_not_represent_contention():
    provider = SimpleNamespace(
        _queue_branch="queue-main",
        _collaboration_git_timeout_seconds=15,
        _run_git_command=lambda *args, **kwargs: (_ for _ in ()).throw(
            TimeoutError("push took too long")
        ),
        _remote_queue_oid=lambda: (_ for _ in ()).throw(
            ConnectionError("no reply")
        ),
    )
    assert not GitSynchronizationProvider._push_queue_branch(
        provider, "new-commit", "old-commit"
    )
    assert provider._last_queue_publication_outcome == "UNKNOWN"


def test_unknown_queue_publication_never_creates_second_candidate():
    calls = {"candidates": 0}
    provider = SimpleNamespace(
        _remote_queue_oid=lambda: "old-commit",
        _read_queue_from_oid=lambda oid: {"requests": []},
        _filter_live_queue_requests=lambda requests: requests,
    )

    def make_candidate(*args):
        calls["candidates"] += 1
        return "new-commit"

    def publish(*args):
        provider._last_queue_publication_outcome = "UNKNOWN"
        return False

    provider._create_queue_commit_plumbing = make_candidate
    provider._push_queue_branch = publish
    assert not GitSynchronizationProvider._mutate_remote_queue(
        provider, lambda requests: (True, requests), retries=5
    )
    assert calls["candidates"] == 1
