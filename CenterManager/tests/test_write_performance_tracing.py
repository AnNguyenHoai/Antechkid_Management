"""No-behavior-change checks for WRITE performance telemetry."""
import logging

import pytest

from centermanager.platform.write_performance import (
    record_git, timed_call, trace_operation,
)


def test_trace_records_safe_phases_and_git_counts(caplog):
    @trace_operation("start")
    def start():
        assert timed_call("request_write", lambda: "GRANTED") == "GRANTED"
        record_git("ls-remote", 3, 40, "returned")
        record_git("push", 2, 99, "error")
        record_git("push", 0, 12, "returned")
        return True

    with caplog.at_level(logging.INFO, logger="centermanager.platform.write_performance"):
        assert start() is True
    summary = next(record.getMessage() for record in caplog.records
                   if "PERF write_trace op=start" in record.getMessage())
    assert "git_calls=3" in summary
    assert "ls-remote:1/40.0" in summary
    assert "push:2/111.0" in summary
    assert "git_failures=push:1" in summary
    assert "request_write:" in summary
    assert "GRANTED" not in summary


def test_trace_preserves_false_return_and_exception(caplog):
    @trace_operation("finish")
    def failed():
        return False

    @trace_operation("finish")
    def raises():
        timed_call("git_publish", lambda: (_ for _ in ()).throw(ValueError("private")))
        return True

    with caplog.at_level(logging.INFO, logger="centermanager.platform.write_performance"):
        assert failed() is False
        with pytest.raises(ValueError, match="private"):
            raises()
    summaries = [r.getMessage() for r in caplog.records
                 if "PERF write_trace op=finish" in r.getMessage()]
    assert len(summaries) == 2
    assert "result=not_completed" in summaries[0]
    assert "result=error" in summaries[1]
    assert "private" not in "\n".join(summaries)


def test_sequential_operations_do_not_share_git_counts(caplog):
    @trace_operation("start")
    def first():
        record_git("fetch", 0, 3, "returned")
        return True

    @trace_operation("finish")
    def second():
        return True

    with caplog.at_level(logging.INFO, logger="centermanager.platform.write_performance"):
        first()
        second()
    summaries = [r.getMessage() for r in caplog.records
                 if "PERF write_trace op=" in r.getMessage()]
    assert "git_calls=1" in summaries[0]
    assert "git_calls=0" in summaries[1]


def test_nested_trace_preserves_parent_operation(caplog):
    @trace_operation("finish")
    def inner():
        record_git("push", 0, 10, "returned")
        return True

    @trace_operation("start")
    def outer():
        return inner()

    with caplog.at_level(logging.INFO, logger="centermanager.platform.write_performance"):
        assert outer()
    summaries = [r.getMessage() for r in caplog.records
                 if "PERF write_trace op=" in r.getMessage()]
    assert len(summaries) == 1
    assert "op=start" in summaries[0]
    assert "push:1/10.0" in summaries[0]
