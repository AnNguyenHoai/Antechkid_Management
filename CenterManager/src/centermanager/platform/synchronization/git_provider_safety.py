"""Thread-safety boundary for Git-backed collaboration providers."""

import threading
from typing import Any


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
        with lock:
            return original_run_git_command(self, *args, **kwargs)

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
