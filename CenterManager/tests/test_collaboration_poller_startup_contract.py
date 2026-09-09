"""Regression coverage for CollaborationPoller startup ordering.

The poller schedules its first asynchronous cycle when started. Collaboration
operations in tests must not race that initial cycle: otherwise a refresh
request can be coalesced with the startup poll and the test can observe an
indeterminate completion boundary.
"""


def test_startup_contract_is_explicit():
    """The shared collaboration visibility tests synchronize initial polling."""
    from pathlib import Path

    path = Path(__file__).parent / "test_collaboration_waiting_visibility.py"
    source = path.read_text(encoding="utf-8")

    assert "initial_spy = QSignalSpy(poller.poll_completed)" in source
    assert "initial poll did not complete" in source
