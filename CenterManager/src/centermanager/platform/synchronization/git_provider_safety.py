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
            # Defensive path for unusual construction/deserialization. Normal
            # provider instances always receive the lock in __init__.
            lock = threading.RLock()
            self._git_command_lock = lock
        with lock:
            return original_run_git_command(self, *args, **kwargs)

    provider_cls.__init__ = init_with_command_lock
    provider_cls._run_git_command = serialized_run_git_command
    provider_cls._git_command_serialization_installed = True
