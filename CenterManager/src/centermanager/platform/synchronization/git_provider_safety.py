"""Thread-safety boundary for Git-backed collaboration providers."""

import logging
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


def install_git_command_serialization(provider_cls: Any) -> None:
    """Serialize Git subprocess access within each provider instance.

    CollaborationPoller executes provider reads from its QThread while the
    application thread can execute lock/synchronization operations on the same
    provider. Git working-tree/object-database operations must not overlap for
    one local repository. The lock is installed here so the provider's existing
    implementation remains unchanged and the synchronization package owns the
    cross-thread infrastructure concern.
    """
    if getattr(provider_cls, "_git_command_serialization_installed", False):
        return

    original_init = provider_cls.__init__
    original_run_git_command = provider_cls._run_git_command

    def init_with_command_lock(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._git_command_lock = threading.RLock()

    def serialized_run_git_command(self, *args, **kwargs):
        lock = getattr(self, "_git_command_lock", None)
        if lock is None:
            lock = threading.RLock()
            self._git_command_lock = lock
        started = time.perf_counter()
        acquired = None
        outcome = "error"
        # Never include argv, URLs, paths, user data or exception text in PERF.
        command_args = args[0] if args else kwargs.get("args", ())
        command = command_args[0] if command_args else "other"
        if command not in {"fetch", "push", "ls-remote", "show", "reset", "commit", "commit-tree"}:
            command = "other"
        try:
            with lock:
                acquired = time.perf_counter()
                result = original_run_git_command(self, *args, **kwargs)
                outcome = "returned"
                return result
        finally:
            finished = time.perf_counter()
            run_started = acquired if acquired is not None else finished
            logger.debug(
                "PERF git command=%s lock_wait_ms=%.1f run_ms=%.1f outcome=%s",
                command,
                (run_started - started) * 1000,
                (finished - run_started) * 1000,
                outcome,
            )

    provider_cls.__init__ = init_with_command_lock
    provider_cls._run_git_command = serialized_run_git_command
    provider_cls._git_command_serialization_installed = True


def install_lock_operation_serialization(provider_cls: Any) -> None:
    """Keep this instance's session/revision token coherent across whole operations."""
    from functools import wraps
    if getattr(provider_cls, "_lock_operation_serialization_installed", False):
        return
    provider_cls._lock_operation_serialization_installed = True

    for name in ("acquire_lock", "renew_lock", "release_lock"):
        original = getattr(provider_cls, name)

        def wrap(operation):
            @wraps(operation)
            def serialized(self, *args, **kwargs):
                if not hasattr(self, "_authority_mutex"):
                    self._authority_mutex = threading.RLock()
                with self._authority_mutex:
                    return operation(self, *args, **kwargs)
            return serialized

        setattr(provider_cls, name, wrap(original))
