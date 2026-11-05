"""Low-risk, request-scoped performance tracing for WRITE collaboration.

Never logs Git argv, paths, business data, credentials or exception messages.
ContextVars intentionally do not propagate to unrelated poller threads.
"""
from collections import Counter, defaultdict
from contextlib import contextmanager
from contextvars import ContextVar
from functools import wraps
import logging
import time
import uuid

logger = logging.getLogger(__name__)
_active_trace = ContextVar("cm_write_perf_trace", default=None)


class _Trace:
    def __init__(self, operation):
        self.id = uuid.uuid4().hex[:12]
        self.operation = operation
        self.started = time.perf_counter()
        self.phases = defaultdict(float)
        self.git_counts = Counter()
        self.git_duration = defaultdict(float)
        self.git_wait_ms = 0.0
        self.git_failures = Counter()
        self.result = "error"

    def summarize(self):
        # Stable labels only: no keys, branch refs, student data or paths.
        phases = ",".join(
            "%s:%.1f" % (k, self.phases[k])
            for k in sorted(self.phases)
        )
        git = ",".join(
            "%s:%d/%.1f" % (k, self.git_counts[k], self.git_duration[k])
            for k in sorted(self.git_counts)
        )
        failures = ",".join(
            "%s:%d" % (k, self.git_failures[k])
            for k in sorted(self.git_failures)
        )
        logger.info(
            "PERF write_trace op=%s id=%s total_ms=%.1f result=%s "
            "git_calls=%d git_wait_ms=%.1f phases_ms=%s git_calls_ms=%s git_failures=%s",
            self.operation, self.id,
            (time.perf_counter() - self.started) * 1000,
            self.result, sum(self.git_counts.values()), self.git_wait_ms,
            phases or "none", git or "none", failures or "none",
        )


def trace_operation(operation):
    """Wrap a synchronous public transaction entrypoint without changing returns."""
    def decorate(func):
        @wraps(func)
        def wrapped(*args, **kwargs):
            if _active_trace.get() is not None:
                return func(*args, **kwargs)
            trace = _Trace(operation)
            token = _active_trace.set(trace)
            logger.info("PERF write_trace_begin op=%s id=%s", operation, trace.id)
            try:
                result = func(*args, **kwargs)
                trace.result = "success" if result else "not_completed"
                return result
            finally:
                _active_trace.reset(token)
                trace.summarize()
        return wrapped
    return decorate


@contextmanager
def trace_phase(name):
    trace = _active_trace.get()
    if trace is None:
        yield
        return
    started = time.perf_counter()
    try:
        yield
    finally:
        duration = (time.perf_counter() - started) * 1000
        trace.phases[name] += duration
        logger.debug(
            "PERF write_phase op=%s id=%s phase=%s ms=%.1f",
            trace.operation, trace.id, name, duration,
        )


def timed_call(name, func, *args, **kwargs):
    with trace_phase(name):
        return func(*args, **kwargs)


def record_git(command, wait_ms, run_ms, outcome):
    trace = _active_trace.get()
    if trace is None:
        return
    # Command is an internal fixed category from the Git serializer.
    command = command if command in {
        "fetch", "push", "ls-remote", "show", "reset", "commit",
        "commit-tree", "other"
    } else "other"
    trace.git_counts[command] += 1
    trace.git_duration[command] += run_ms
    trace.git_wait_ms += wait_ms
    if outcome != "returned":
        trace.git_failures[command] += 1
